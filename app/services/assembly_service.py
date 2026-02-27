from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings
from app.schemas import ClipVariant, ScriptOption
from app.utils.ffmpeg_tools import concat_videos


class AssemblyService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def local_assembly_enabled(self) -> bool:
        return self._settings.local_assembly_enabled

    def choose_variants(
        self,
        script: ScriptOption,
        variants: dict[str, list[ClipVariant]],
        preferred: dict[str, int],
    ) -> dict[str, ClipVariant]:
        chosen: dict[str, ClipVariant] = {}
        for shot in script.shots:
            options = variants.get(shot.shot_id, [])
            if not options:
                continue

            preferred_index = preferred.get(shot.shot_id)
            if preferred_index is not None:
                picked = next((x for x in options if x.variant_index == preferred_index), None)
                if picked:
                    chosen[shot.shot_id] = picked
                    continue

            chosen[shot.shot_id] = max(options, key=lambda clip: clip.score)
        return chosen

    def write_subtitles(self, project_id: str, script: ScriptOption) -> Path:
        subtitle_path = self._render_dir(project_id) / "subtitles.srt"
        cursor = 0
        rows: list[str] = []

        for idx, shot in enumerate(script.shots, start=1):
            start = self._format_srt_time(cursor)
            cursor += shot.duration_sec
            end = self._format_srt_time(cursor)
            rows.extend([str(idx), f"{start} --> {end}", shot.on_screen_text, ""])

        subtitle_path.write_text("\n".join(rows), encoding="utf-8")
        return subtitle_path

    def assemble_video(
        self,
        project_id: str,
        chosen: dict[str, ClipVariant],
        script: ScriptOption,
    ) -> tuple[Path | None, Path, str]:
        render_dir = self._render_dir(project_id)
        subtitle_path = self.write_subtitles(project_id, script)

        ordered = [chosen.get(shot.shot_id) for shot in script.shots]
        video_paths = [Path(item.local_path) for item in ordered if item and item.local_path]

        if self._settings.local_assembly_enabled and video_paths:
            if concat_videos(video_paths, render_dir / "final.mp4"):
                return (
                    render_dir / "final.mp4",
                    subtitle_path,
                    "云端素材生成完成，并已在本地自动拼接为 final.mp4。",
                )
            note = "云端素材生成完成，但本地自动拼接失败（通常是 ffmpeg 不可用）。"
        elif not self._settings.local_assembly_enabled:
            note = "云端素材生成完成。当前未启用本地自动拼接（MVP 默认关闭）。"
        else:
            note = "云端素材生成完成，但没有可拼接的本地片段。"

        manifest_path = render_dir / "render_manifest.json"
        manifest = {
            "project_id": project_id,
            "note": note,
            "shots": [
                {
                    "shot_id": shot.shot_id,
                    "duration_sec": shot.duration_sec,
                    "narration": shot.narration,
                    "on_screen_text": shot.on_screen_text,
                    "clip": (
                        chosen.get(shot.shot_id).model_dump()
                        if chosen.get(shot.shot_id)
                        else None
                    ),
                }
                for shot in script.shots
            ],
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return None, subtitle_path, note

    def _format_srt_time(self, seconds: int) -> str:
        hh = seconds // 3600
        mm = (seconds % 3600) // 60
        ss = seconds % 60
        return f"{hh:02d}:{mm:02d}:{ss:02d},000"

    def _render_dir(self, project_id: str) -> Path:
        path = self._settings.storage_root / "renders" / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path
