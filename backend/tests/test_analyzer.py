import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.parser import SourceScanStats
from app.services.analyzer import _format_scan_progress_detail


def test_scan_progress_detail_shows_true_counts_and_truncation():
    detail = _format_scan_progress_detail(
        SourceScanStats(
            discovered_files=320,
            unsupported_extension_files=80,
            supported_extension_files=240,
            ignored_files=25,
            parsed_files=215,
        ),
        total_source_files=215,
        analyzed_files=200,
        truncated_files=15,
    )

    assert "发现 320 个文件" in detail
    assert "非源码/不支持后缀 80 个" in detail
    assert "过滤配置/测试/构建/生成文件 25 个" in detail
    assert "业务源码 215 个" in detail
    assert "本次分析 200 个" in detail
    assert "已截断 15 个" in detail


def test_scan_progress_detail_says_when_limit_not_hit():
    detail = _format_scan_progress_detail(
        SourceScanStats(
            discovered_files=30,
            unsupported_extension_files=10,
            supported_extension_files=20,
            ignored_files=3,
            parsed_files=17,
        ),
        total_source_files=17,
        analyzed_files=17,
        truncated_files=0,
    )

    assert "本次分析 17 个" in detail
    assert "未触发 200 上限" in detail
