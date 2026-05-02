import argparse
import io
import os
import shutil
import struct
import subprocess
import sys
import traceback
from pathlib import Path
from typing import List, Optional, Tuple

# this preprocesses lots of assets to massively improve performance
# edited by owen before committing to add some fixes
# works best on Linux, works on windows?

# I honestly forgot where I got this libary from, please rework this and use a different libary if someone can do that, this lib sucks to work with.

try:
    from PIL import Image
except ImportError:
    print("Pillow not found install with: pip install Pillow")
    sys.exit(1)

try:
    import zlib
except ImportError:
    print("ERROR: zlib module not found")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))

from datawin_py import DataWin, DataWinParserOptions

PIXEL_CACHE_MAGIC = b"C3CP"
PIXEL_CACHE_HEADER_SIZE = 16


class TextureExtractor:
    """does the thing"""

    def __init__(self, data_win_path: str, output_dir: str = "gfx"):
        self.data_win_path = Path(data_win_path)
        self.output_dir = Path(output_dir)
        self.dw: Optional[DataWin] = None
        self.texture_pages: List[Optional[Image.Image]] = []

    def load_data_win(self):
        # load file
        print(f"Loading data.win from {self.data_win_path}...")
        self.dw = DataWin.load(str(self.data_win_path))
        print(f"Loaded game: {self.dw.gen8.name} version: {self.dw.gen8.major}.{self.dw.gen8.minor}")
        print(f"Sprites len: {len(self.dw.sprt.sprites)}")
        print(f"Backgrounds len: {len(self.dw.bgnd.backgrounds)}")
        print(f"Textures len: {len(self.dw.txtr.textures)}")

    def extract_texture_pages(self):
        # grab pages
        if not self.dw:
            raise RuntimeError("data.win not loaded???????????????????")

        print(f"\npulling {len(self.dw.txtr.textures)} texture pages")
        self.texture_pages = []

        with open(self.data_win_path, "rb") as f:
            for i, texture in enumerate(self.dw.txtr.textures):
                print(f"  Page {i}...", end=" ", flush=True)

                if texture.blob_offset == 0:
                    print("skip")
                    self.texture_pages.append(None)
                    continue

                try:
                    f.seek(texture.blob_offset)
                    blob_data = f.read(texture.blob_size)
                    img = Image.open(io.BytesIO(blob_data))
                    img.load()
                    self.texture_pages.append(img)
                    print(f"ok {img.width}x{img.height}")
                except Exception as e:
                    print(f"bad {e}")
                    self.texture_pages.append(None)

    def export_sd_pixel_cache(self, cache_dir: str = "cache"):
        # write cache
        if not self.dw:
            raise RuntimeError("data.win not loaded")

        if not self.texture_pages:
            print("No texture pages loaded")
            return

        out_dir = Path(cache_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nputting cache at {out_dir}/...")

        written = 0
        skipped = 0
        failed = 0

        for i, texture in enumerate(self.dw.txtr.textures):
            if texture.blob_offset == 0:
                skipped += 1
                continue

            page_img = self.texture_pages[i] if i < len(self.texture_pages) else None
            if page_img is None:
                print(f"  page_{i}.bin: bad page")
                failed += 1
                continue

            try:
                rgba = page_img.convert("RGBA")
                w, h = rgba.size
                pixels = rgba.tobytes()
                header = struct.pack("<4sIII", PIXEL_CACHE_MAGIC, w, h, texture.blob_size)

                if len(header) != PIXEL_CACHE_HEADER_SIZE:
                    raise RuntimeError(f"bad header size {len(header)}")

                out_path = out_dir / f"page_{i}.bin"
                with open(out_path, "wb") as f:
                    f.write(header)
                    f.write(pixels)

                written += 1
            except Exception as e:
                print(f"  page_{i}.bin: bad {e}")
                failed += 1

        font_pages = set()
        for font in self.dw.font.fonts:
            tpag_idx = self.dw.tpag.offset_map.get(font.texture_offset)
            if tpag_idx is None or tpag_idx >= len(self.dw.tpag.items):
                continue
            page_id = self.dw.tpag.items[tpag_idx].texture_page_id
            if page_id >= 0:
                font_pages.add(page_id)

        missing_font_pages = [
            p for p in sorted(font_pages) if not (out_dir / f"page_{p}.bin").exists()
        ]

        print(f"\nOK wrote {written} cache pages, skipped {skipped}, failed {failed}")
        if font_pages:
            print(f"Font pages: {sorted(font_pages)}")
        if missing_font_pages:
            print(f"WARN missing font pages: {missing_font_pages}")
        else:
            if font_pages:
                print("OK font pages are there!!!")

        print("Copy cache files to romfs/cinnamon/cache/")

    def extract_sprites(self):
        # cut sprites (TODO: needs improvement can be buggy)
        if not self.dw:
            raise RuntimeError("data.win not loaded")

        if not self.texture_pages:
            print("No texture pages loaded")
            return

        print(f"\nExtracting sprites...")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        sprite_count = 0

        for sprite_idx, sprite in enumerate(self.dw.sprt.sprites):
            if not sprite.name:
                print(f" Sprite {sprite_idx}: skip")
                continue

            print(f" Sprite {sprite_idx}: {sprite.name}")
            sprite_dir = self.output_dir / sprite.name
            sprite_dir.mkdir(parents=True, exist_ok=True)

            png_files = []

            for frame_idx, file_offset in enumerate(sprite.texture_offsets):
                try:
                    tpag_idx = self.dw.tpag.offset_map.get(file_offset)
                    if tpag_idx is None:
                        print(f"    Frame {frame_idx}: no offset")
                        continue
                    if tpag_idx >= len(self.dw.tpag.items):
                        print(f"    Frame {frame_idx}: bad tpag index {tpag_idx}")
                        continue

                    tpag_item = self.dw.tpag.items[tpag_idx]
                    texture_page_id = tpag_item.texture_page_id

                    if not (0 <= texture_page_id < len(self.texture_pages)):
                        print(f"    Frame {frame_idx}: bad page id {texture_page_id}")
                        continue

                    page_img = self.texture_pages[texture_page_id]
                    if page_img is None:
                        print(f"    Frame {frame_idx}: page not loaded")
                        continue

                    src_x = tpag_item.source_x
                    src_y = tpag_item.source_y
                    src_w = tpag_item.source_width
                    src_h = tpag_item.source_height

                    tgt_w = tpag_item.bounding_width or src_w
                    tgt_h = tpag_item.bounding_height or src_h

                    frame_img = Image.new("RGBA", (tgt_w, tgt_h), (0, 0, 0, 0))

                    src_box = (
                        src_x,
                        src_y,
                        min(src_x + src_w, page_img.width),
                        min(src_y + src_h, page_img.height),
                    )
                    crop = page_img.crop(src_box)

                    tgt_x = tpag_item.target_x
                    tgt_y = tpag_item.target_y
                    frame_img.paste(crop, (tgt_x, tgt_y), crop if crop.mode == "RGBA" else None)

                    frame_path = sprite_dir / f"{sprite.name}_{frame_idx}.png"
                    frame_img.save(str(frame_path), "PNG")
                    png_files.append(frame_path.name)

                    print(f"    OK {frame_path.name}")
                except Exception as e:
                    # crap. AHHHHHHHHHHHHHH
                    print(f"    BAD frame {frame_idx}: {e}")

            if png_files:
                self.generate_t3s_file(sprite_dir, sprite.name, png_files)

            sprite_count += 1

        print(f"\nOK extracted {sprite_count} sprites")

    def extract_backgrounds(self):
        # backgrounds added!!! =D
        if not self.dw:
            raise RuntimeError("data.win not loaded")

        if not self.texture_pages:
            print("No texture pages loaded")
            return

        print(f"\nExtracting backgrounds...")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        background_count = 0

        for bg_idx, background in enumerate(self.dw.bgnd.backgrounds):
            if not background.name:
                print(f"  Background {bg_idx}: skip")
                continue

            print(f"  Background {bg_idx}: {background.name}")
            bg_dir = self.output_dir / background.name
            bg_dir.mkdir(parents=True, exist_ok=True)

            try:
                tpag_idx = self.dw.tpag.offset_map.get(background.texture_offset)
                if tpag_idx is None:
                    print(f"    no offset {background.texture_offset}")
                    continue
                if tpag_idx >= len(self.dw.tpag.items):
                    print(f"    bad tpag index {tpag_idx}")
                    continue

                tpag_item = self.dw.tpag.items[tpag_idx]
                texture_page_id = tpag_item.texture_page_id

                if not (0 <= texture_page_id < len(self.texture_pages)):
                    print(f"    bad page id {texture_page_id}")
                    continue

                page_img = self.texture_pages[texture_page_id]
                if page_img is None:
                    print(f"    page not loaded")
                    continue

                src_x = tpag_item.source_x
                src_y = tpag_item.source_y
                src_w = tpag_item.source_width
                src_h = tpag_item.source_height
                tgt_w = tpag_item.bounding_width or src_w
                tgt_h = tpag_item.bounding_height or src_h

                frame_img = Image.new("RGBA", (tgt_w, tgt_h), (0, 0, 0, 0))
                src_box = (
                    src_x,
                    src_y,
                    min(src_x + src_w, page_img.width),
                    min(src_y + src_h, page_img.height),
                )
                crop = page_img.crop(src_box)

                tgt_x = tpag_item.target_x
                tgt_y = tpag_item.target_y
                frame_img.paste(crop, (tgt_x, tgt_y), crop if crop.mode == "RGBA" else None)

                frame_path = bg_dir / f"{background.name}_0.png"
                frame_img.save(str(frame_path), "PNG")

                self.generate_t3s_file(bg_dir, background.name, [frame_path.name])

                print(f"    OK {frame_path.name}")
                background_count += 1
            except Exception as e:
                print(f"    BAD {e}")
                traceback.print_exc()

        print(f"\nOK extracted {background_count} backgrounds")

    def generate_t3s_file(self, sprite_dir: Path, sprite_name: str, png_files: List[str]):
        # make t3s for compression
        t3s_path = sprite_dir / f"{sprite_name}.t3s"

        lines = []
        if len(png_files) > 1:
            lines.append("--atlas")

        # TODO low priority: figure out how to compress less, it looks crap on upscaled emu
        lines.append("-f etc1a4")
        lines.append("-z auto")
        lines.extend(png_files)

        with open(t3s_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        print(f"    OK {t3s_path.name}")

    def extract_audio(self):
        # sound time
        if not self.dw:
            raise RuntimeError("data.win not loaded")

        sounds = self.dw.sond.sounds
        entries = self.dw.audo.entries
        data_win_dir = self.data_win_path.parent
        project_root = Path.cwd()
        sfx_root = project_root / "sfx"

        # TODO: low prority could use improvement, works for now
        base = Path(__file__).parent / "tools"
        bannertool = base / ("bannertool.exe" if os.name == "nt" else "bannertool")
        if not bannertool.exists():
            print(f"  WARN bannertool missing at {bannertool}, skipping audio, why did you remove it from tools???")
            return

        if os.name != "nt" and not os.access(str(bannertool), os.X_OK):
            try:
                bannertool.chmod(bannertool.stat().st_mode | 0o111)
            except Exception:
                pass

        def choose_audio_profile(name: str, sound_file: str) -> Tuple[int, int, str]:
            name_l = (name or "").lower()
            file_l = (sound_file or "").lower()
            is_music = (
                name_l.startswith("mus_")
                or "mus" in file_l
                or file_l.startswith("mus_")
            )
            if is_music:
                return 32000, 1, "music"
            return 22050, 1, "sfx"

        def nearest_supported_rate(rate: int) -> int:
            supported = [8000, 11025, 16000, 22050, 32000]
            if rate <= supported[0]:
                return supported[0]
            if rate >= supported[-1]:
                return supported[-1]
            best = supported[0]
            for s in supported:
                if s <= rate:
                    best = s
            return best

        def probe_media(path: Path) -> Optional[Tuple[int, int]]:
            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-select_streams",
                        "a:0",
                        "-show_entries",
                        "stream=sample_rate,channels",
                        "-of",
                        "default=nokey=1:noprint_wrappers=1",
                        str(path),
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return None
                lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
                if len(lines) < 2:
                    return None
                sr = int(lines[0])
                ch = int(lines[1])
                if sr <= 0 or ch <= 0:
                    return None
                return sr, ch
            except Exception:
                return None

        def make_cwav(wav_path: Path, cwav_path: Path, is_music: bool) -> bool:
            cmd = [str(bannertool), "makecwav", "-i", str(wav_path), "-o", str(cwav_path)]
            if is_music:
                cmd += ["-l"]
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0

        def resolve_external_audio(sound_file: str) -> Optional[Path]:
            if not sound_file:
                return None

            sf = Path(sound_file)
            base = sf.name

            candidates = [
                sf,
                data_win_dir / sound_file,
                data_win_dir / base,
                data_win_dir / "mus" / base,
                data_win_dir / "audio" / base,
                project_root / sound_file,
                project_root / base,
                project_root / "mus" / base,
                project_root / "audio" / base,
                sfx_root / sound_file,
                sfx_root / base,
                sfx_root / "mus" / base,
                sfx_root / "audio" / base,
            ]

            for c in candidates:
                if c.exists() and c.is_file():
                    return c
            return None

        if not sounds:
            print("No sounds found")
            return

        print(f"\nExtracting {len(sounds)} audio entries...")

        audio_dir = Path("romfs/audio")
        audio_dir.mkdir(parents=True, exist_ok=True)

        success_count = 0

        with open(self.data_win_path, "rb") as f:
            for sound in sounds:
                name = sound.name
                if not name:
                    continue

                print(f"  {name}...", end=" ", flush=True)

                tmp_wav = None
                try:
                    out_path = audio_dir / f"{name}.cwav"
                    tmp_wav = audio_dir / f"{name}_tmp.wav"

                    target_sr, target_ch, profile = choose_audio_profile(name, sound.file)
                    ext_src = resolve_external_audio(sound.file)

                    if ext_src is not None:
                        probed = probe_media(ext_src)
                        if probed is not None:
                            src_sr, src_ch = probed
                            target_sr = min(target_sr, nearest_supported_rate(src_sr))
                            target_ch = 1 if profile == "music" else max(1, min(src_ch, 1))

                        ffmpeg_result = subprocess.run(
                            [
                                "ffmpeg",
                                "-y",
                                "-i",
                                str(ext_src),
                                "-ar",
                                str(target_sr),
                                "-ac",
                                "1",
                                str(tmp_wav),
                            ],
                            capture_output=True,
                        )
                    else:
                        audio_idx = sound.audio_file
                        if audio_idx < 0 or audio_idx >= len(entries):
                            print(f"\033[31mFAILED: audio_file index {audio_idx} out of range\033[0m")
                            continue

                        entry = entries[audio_idx]
                        if entry.data_size == 0:
                            print("\033[31mFAILED: empty audio entry\033[0m")
                            continue

                        # Shut up
                        #if name.startswith("mus_") and entry.data_size < 128 * 1024:
                            #print(
                            #    f"\033[33mWARN: small AUDO entry ({entry.data_size} B) for music\033[0m"
                            #)

                        f.seek(entry.data_offset)
                        raw_data = f.read(entry.data_size)

                        ffmpeg_result = subprocess.run(
                            [
                                "ffmpeg",
                                "-y",
                                "-i",
                                "pipe:0",
                                "-ar",
                                str(target_sr),
                                "-ac",
                                "1",
                                str(tmp_wav),
                            ],
                            input=raw_data,
                            capture_output=True,
                        )

                    if ffmpeg_result.returncode != 0:
                        err = ffmpeg_result.stderr.decode(errors="replace").splitlines()
                        last = err[-1] if err else "ffmpeg failed"
                        print(f"\033[31mFAILED: {last}\033[0m")
                        continue

                    if not make_cwav(tmp_wav, out_path, profile == "music"):
                        print("\033[31mFAILED: bannertool makecwav failed\033[0m")
                        continue

                    if sound.file:
                        file_stem = Path(sound.file).stem
                        if file_stem and file_stem != name:
                            alias_path = audio_dir / f"{file_stem}.cwav"
                            if alias_path != out_path:
                                shutil.copyfile(out_path, alias_path)

                    print("\033[32mOK\033[0m")
                    success_count += 1

                except Exception as e:
                    print(f"\033[31mFAILED: {e}\033[0m")
                    traceback.print_exc()
                finally:
                    if tmp_wav and tmp_wav.exists():
                        try:
                            tmp_wav.unlink()
                        except Exception:
                            pass

        print(f"\n\033[32mOK extracted {success_count} audio files to romfs/audio/\033[0m")

    def run(self, cache_dir: str = "cache"):
        # extract everything, TODO: extract rooms and other data to a easily readable (by 3ds cpu) format
        # TODO: add more compression.
        try:
            self.load_data_win()
            self.extract_texture_pages()
            self.export_sd_pixel_cache(cache_dir)
            self.extract_sprites()
            self.extract_backgrounds()
            self.extract_audio()
            print(f"\n\033[32mOK Complete! Sprites saved to {self.output_dir}/\033[0m")
        except Exception as e:
            print(f"\033[31mFAILED: {e}\033[0m")
            traceback.print_exc()
            sys.exit(1)


def main():
    # parse args
    parser = argparse.ArgumentParser(
        description="Extract sprites/backgrounds/audio and 3DS cache pages from data.win"
    )
    parser.add_argument("data_win_path", help="Path to data.win")
    parser.add_argument("output_dir", nargs="?", default="gfx", help="Output dir")
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Only generate page_N.bin cache files",
    )
    parser.add_argument(
        "--cache-dir",
        default="cache",
        help="Directory where page_N.bin cache files are written",
    )

    args = parser.parse_args()

    if not Path(args.data_win_path).exists():
        print(f"Error: {args.data_win_path} not found")
        sys.exit(1)

    extractor = TextureExtractor(args.data_win_path, args.output_dir)

    if args.cache_only:
        try:
            extractor.load_data_win()
            extractor.extract_texture_pages()
            extractor.export_sd_pixel_cache(args.cache_dir)
            print("\n\033[32mOK Cache export complete\033[0m")
        except Exception as e:
            print(f"\033[31mFAILED: {e}\033[0m")
            traceback.print_exc()
            sys.exit(1)
    else:
        extractor.run(cache_dir=args.cache_dir)


if __name__ == "__main__":
    main()
