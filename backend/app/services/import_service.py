"""项目导入服务 — GitHub clone + zip 解压"""

import subprocess
import tempfile
import zipfile
import tarfile
import shutil
import os
from pathlib import Path
from typing import Optional

from app.config import settings


class ImportService:
    """负责从各种来源导入项目源码到临时目录"""

    async def import_from_github(self, repo_url: str, branch: str = "") -> str:
        """Clone GitHub 仓库到临时目录，返回目录路径"""
        tmpdir = tempfile.mkdtemp(prefix="poltai_gh_")
        clean_url = repo_url.rstrip("/")
        if not clean_url.endswith(".git"):
            clean_url += ".git"

        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd.extend(["-b", branch])
        cmd.extend([clean_url, tmpdir])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,  # 30 秒超时，足够小仓库，大仓库建议上传 zip
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_HTTP_LOW_SPEED_LIMIT": "1000", "GIT_HTTP_LOW_SPEED_TIME": "10"},
            )
            if result.returncode != 0:
                stderr = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
                raise RuntimeError(f"Git clone 失败: {stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Git clone 超时（>30秒），网络可能不可达，建议下载 zip 后上传")
        except FileNotFoundError:
            raise RuntimeError("系统未安装 git，请先安装 git")

        # 验证目录
        if not list(Path(tmpdir).iterdir()):
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise RuntimeError("克隆的仓库为空")

        return tmpdir

    async def import_from_upload(self, file_path: str) -> str:
        """解压上传的文件到临时目录，返回源码根目录路径"""
        tmpdir = tempfile.mkdtemp(prefix="poltai_up_")

        try:
            self._extract(file_path, tmpdir)
        except Exception as e:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise RuntimeError(f"解压失败: {e}")

        # 智能检测根目录：如果解压后只有一个文件夹，进入该文件夹
        root = Path(tmpdir)
        entries = list(root.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            return str(entries[0])

        return tmpdir

    def _extract(self, file_path: str, dest: str):
        path = Path(file_path)
        if path.suffix == ".zip":
            with zipfile.ZipFile(file_path, "r") as zf:
                zf.extractall(dest)
        elif path.suffix in (".gz", ".tgz") or ".tar" in path.suffix:
            with tarfile.open(file_path, "r:*") as tf:
                tf.extractall(dest)
        else:
            raise ValueError(f"不支持的文件格式: {path.suffix}")

    def cleanup(self, tmpdir: str):
        """清理临时目录"""
        shutil.rmtree(tmpdir, ignore_errors=True)


# 单例
import_service = ImportService()
