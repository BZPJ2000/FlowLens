"""RuleAnalyzer 单元测试 — 验证 ParseResult → AIFileAnalysis 规则转换"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.schemas import (
    AIInputOutput,
    ClassDefinition,
    ExportInfo,
    FunctionSignature,
    ImportInfo,
    ParseResult,
)
from app.core.rule_analyzer import RuleAnalyzer


# ── 角色分类：目录路径 ────────────────────────────

def test_classify_role_by_directory_path():
    cases = [
        ("/home/project/controllers/user.go", "controller"),
        ("src/services/auth.py", "service"),
        ("lib/models/User.ts", "model"),
        ("app/views/Home.tsx", "view"),
        ("src/components/Button.tsx", "view"),
        ("pages/index.tsx", "view"),
        ("src/utils/format.ts", "util"),
        ("common/helpers/date.ts", "util"),
        ("config/app.py", "config"),
        ("middleware/auth.ts", "middleware"),
        ("hooks/useAuth.ts", "hook"),
        ("store/index.ts", "store"),
        ("types/index.ts", "type"),
        ("__tests__/app.test.ts", "test"),
        ("routes/api.ts", "route"),
    ]
    ra = RuleAnalyzer()
    for file_path, expected in cases:
        assert ra._classify_role(file_path) == expected, f"{file_path} → {expected}"


# ── 角色分类：文件名 ──────────────────────────────

def test_classify_role_by_filename_pattern():
    cases = [
        ("src/app/UserController.ts", "controller"),
        ("src/app/AuthHandler.ts", "controller"),
        ("src/app/route.ts", "controller"),
        ("src/app/UserService.ts", "service"),
        ("src/app/AuthLogic.ts", "service"),
        ("src/app/UserDomain.ts", "service"),
        ("src/app/UserModel.ts", "model"),
        ("src/app/UserEntity.ts", "model"),
        ("src/app/UserSchema.ts", "model"),
        ("src/app/UserDto.ts", "model"),
        ("src/app/UserRepository.ts", "model"),
        ("src/app/dateUtil.ts", "util"),
        ("src/app/formatHelper.ts", "util"),
        ("src/app/dbLib.ts", "util"),
        ("src/app/CommonTool.ts", "util"),
        ("src/app/appConfig.ts", "config"),
        ("src/app/appSetting.ts", "config"),
        ("src/app/env.ts", "config"),
        ("src/app/Option.ts", "config"),
        ("src/app/authMiddleware.ts", "middleware"),
        ("src/app/headerInterceptor.ts", "middleware"),
        ("src/app/authFilter.ts", "middleware"),
        ("src/app/permissionGuard.ts", "middleware"),
        ("src/app/useAuth.ts", "hook"),
        ("src/app/usePagination.ts", "hook"),
        ("src/app/Composable.ts", "hook"),
        ("src/app/appStore.ts", "store"),
        ("src/app/userAtom.ts", "store"),
        ("src/app/AuthState.ts", "store"),
        ("src/app/UserType.ts", "type"),
        ("src/types/IUser.ts", "type"),
        ("src/app/UserEnum.ts", "type"),
        ("src/app/types.ts", "type"),
        ("src/app/app.test.ts", "test"),
        ("src/app/app.spec.ts", "test"),
        ("src/app/router.ts", "route"),
        ("src/app/HomeView.tsx", "view"),
        ("src/app/ButtonComponent.tsx", "view"),
        ("src/app/MainPage.tsx", "view"),
        ("src/app/DefaultLayout.tsx", "view"),
    ]
    ra = RuleAnalyzer()
    for file_path, expected in cases:
        assert ra._classify_role(file_path) == expected, f"{file_path} → {expected}"


# ── 角色分类：目录优先于文件名 ────────────────────

def test_classify_role_directory_priority_over_filename():
    """当目录是 /services/ 但文件名含 controller 时，目录胜出"""
    ra = RuleAnalyzer()
    result = ra._classify_role("src/services/UserController.ts")
    assert result == "service"


def test_classify_role_fallback_to_other():
    cases = [
        "src/random_stuff/whatever.py",
        "src/app/unknown.cs",
        "main.go",
    ]
    ra = RuleAnalyzer()
    for file_path in cases:
        assert ra._classify_role(file_path) == "other", f"{file_path} → other"


# ── 摘要生成 ──────────────────────────────────────

def test_build_summary_with_functions_and_classes():
    ra = RuleAnalyzer()
    pr = ParseResult(
        file_path="src/app/UserService.ts",
        file_name="UserService.ts",
        language="typescript",
        functions=[
            FunctionSignature(name="fetchUser", params=[{"name": "id", "type": "string"}], return_type="Promise"),
            FunctionSignature(name="updateUser", params=[{"name": "dto", "type": "UserDto"}], return_type="void"),
            FunctionSignature(name="deleteUser", params=[{"name": "id", "type": "string"}], return_type="void"),
        ],
        classes=[
            ClassDefinition(name="UserService", methods=[]),
        ],
    )
    summary = ra._build_summary(pr)
    assert "3个函数" in summary
    assert "1个类" in summary
    assert "fetchUser" in summary
    assert "updateUser" in summary
    assert "UserService" in summary


def test_build_summary_truncates_long_lists():
    ra = RuleAnalyzer()
    pr = ParseResult(
        file_path="src/app/utils.ts",
        file_name="utils.ts",
        language="typescript",
        functions=[
            FunctionSignature(name=f"fn{i}", params=[], return_type="void")
            for i in range(10)
        ],
        classes=[],
    )
    summary = ra._build_summary(pr)
    assert "等" in summary
    assert len(pr.functions) == 10


def test_build_summary_no_functions_no_classes():
    ra = RuleAnalyzer()
    pr = ParseResult(
        file_path="src/types/index.ts",
        file_name="index.ts",
        language="typescript",
    )
    summary = ra._build_summary(pr)
    assert "typescript" in summary


# ── 详情生成 ──────────────────────────────────────

def test_build_detail_imports_exports_counts():
    ra = RuleAnalyzer()
    pr = ParseResult(
        file_path="src/app/UserService.ts",
        file_name="UserService.ts",
        language="typescript",
        imports=[
            ImportInfo(variable_name="User", source_module="./UserDto"),
            ImportInfo(variable_name="api", source_module="../api/client"),
        ],
        exports=[
            ExportInfo(variable_name="createUser", data_type="function", is_function=True),
            ExportInfo(variable_name="UserSchema", data_type="object"),
        ],
        functions=[],
        classes=[],
        line_count=42,
    )
    detail = ra._build_detail(pr)
    assert "2 个外部依赖" in detail
    assert "2 个符号" in detail
    assert "42 行代码" in detail


# ── 输入输出映射 ──────────────────────────────────

def test_map_inputs_from_parse_imports():
    ra = RuleAnalyzer()
    pr = ParseResult(
        file_path="src/services/auth.ts",
        file_name="auth.ts",
        language="typescript",
        imports=[
            ImportInfo(variable_name="jwt", source_module="jsonwebtoken", data_type="object", import_type="named"),
            ImportInfo(variable_name="User", source_module="../models/User", data_type="User", import_type="named", alias="UserModel"),
        ],
    )
    inputs = ra._map_inputs(pr)
    assert len(inputs) == 2
    assert all(isinstance(i, AIInputOutput) for i in inputs)
    assert inputs[0].name == "jwt"
    assert inputs[0].source == "jsonwebtoken"
    assert inputs[0].type == "object"
    assert inputs[1].name == "User"
    assert inputs[1].source == "../models/User"


def test_map_outputs_from_parse_exports():
    ra = RuleAnalyzer()
    pr = ParseResult(
        file_path="src/services/auth.ts",
        file_name="auth.ts",
        language="typescript",
        exports=[
            ExportInfo(variable_name="login", data_type="function", is_function=True),
            ExportInfo(variable_name="logout", data_type="function", is_function=True),
            ExportInfo(variable_name="AuthConfig", data_type="object", is_class=True),
        ],
    )
    outputs = ra._map_outputs(pr)
    assert len(outputs) == 3
    assert all(isinstance(o, AIInputOutput) for o in outputs)
    assert outputs[0].name == "login"
    assert outputs[0].is_function is True
    assert outputs[1].name == "logout"
    assert outputs[2].name == "AuthConfig"
    assert outputs[2].is_function is False


# ── 依赖摘要 ───────────────────────────────────────

def test_deps_summary_with_external_deps():
    ra = RuleAnalyzer()
    pr = ParseResult(
        file_path="src/services/auth.ts",
        file_name="auth.ts",
        language="typescript",
        imports=[
            ImportInfo(variable_name="jwt", source_module="jsonwebtoken"),
            ImportInfo(variable_name="bcrypt", source_module="bcrypt"),
            ImportInfo(variable_name="express", source_module="express"),
            ImportInfo(variable_name="User", source_module="../models/User"),  # 内部，不计数
        ],
    )
    deps = ra._build_deps_summary(pr, "service")
    assert "4 个" in deps or "4个" in deps
    # 外部包应被提取
    assert "jsonwebtoken" in deps or "express" in deps or "bcrypt" in deps


def test_deps_summary_no_imports():
    ra = RuleAnalyzer()
    pr = ParseResult(
        file_path="src/types/index.ts",
        file_name="index.ts",
        language="typescript",
    )
    deps = ra._build_deps_summary(pr, "type")
    assert "无外部依赖" in deps


# ── 完整 analyze 输出 ─────────────────────────────

def test_analyze_produces_complete_aifileanalysis():
    ra = RuleAnalyzer()
    pr = ParseResult(
        file_path="src/services/auth.py",
        file_name="auth.py",
        language="python",
        imports=[
            ImportInfo(variable_name="User", source_module="models.user", import_type="named", data_type="User"),
        ],
        exports=[
            ExportInfo(variable_name="login", data_type="function", is_function=True),
        ],
        functions=[
            FunctionSignature(name="login", params=[{"name": "username", "type": "str"}, {"name": "password", "type": "str"}], return_type="bool", is_exported=True),
        ],
        classes=[],
        line_count=30,
    )
    result = ra.analyze(pr)
    assert result.file_path == "src/services/auth.py"
    assert result.architecture_role == "service"
    assert len(result.inputs) == 1
    assert result.inputs[0].name == "User"
    assert len(result.outputs) == 1
    assert result.outputs[0].name == "login"
    assert "login" in result.summary
    assert "1个函数" in result.summary
    assert "30 行" in result.detail


# ── 批量分析 ───────────────────────────────────────

def test_analyze_batch_returns_same_count():
    ra = RuleAnalyzer()
    parse_results = [
        ParseResult(
            file_path=f"src/controllers/{name}.ts",
            file_name=f"{name}.ts",
            language="typescript",
            imports=[ImportInfo(variable_name="api", source_module="./api")],
        )
        for name in ["user", "order", "product", "auth", "cart"]
    ]
    results = ra.analyze_batch(parse_results)
    assert len(results) == 5
    for r in results:
        assert r.architecture_role == "controller"


# ── 边界条件 ───────────────────────────────────────

def test_analyze_empty_parse_result():
    ra = RuleAnalyzer()
    pr = ParseResult(
        file_path="src/app/empty.py",
        file_name="empty.py",
        language="python",
    )
    result = ra.analyze(pr)
    assert result.file_path == "src/app/empty.py"
    assert result.architecture_role == "other"
    assert result.inputs == []
    assert result.outputs == []


def test_windows_paths_normalized():
    ra = RuleAnalyzer()
    result = ra._classify_role(r"src\controllers\user.go")
    assert result == "controller"


def test_role_patterns_are_case_insensitive():
    ra = RuleAnalyzer()
    assert ra._classify_role("src/app/CONTROLLER.cs") == "controller"
    assert ra._classify_role("src/app/Service.ts") == "service"
    assert ra._classify_role("src/app/Model.ts") == "model"
