"""Multi-language parser extraction tests — Go, Java, C, C++, C#, Rust, Ruby, Swift, Kotlin, Vue, Svelte, Bash"""
import sys, textwrap
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.parser import CodeParser

parser = CodeParser()


def _make_result(content: str, lang: str) -> dict:
    """Parse inline content for a given language and return dict of extractions."""
    return {
        "imports": parser._extract_imports(content, lang),
        "exports": parser._extract_exports(content, lang),
        "functions": parser._extract_functions(content, lang),
        "classes": parser._extract_classes(content, lang),
        "calls": parser._extract_calls(content, lang),
    }


# ── Go ────────────────────────────────────────

GO_CODE = textwrap.dedent("""\
package main

import (
    "fmt"
    "net/http"
)

func Login(user string, pass string) (bool, error) {
    fmt.Println("login")
    return true, nil
}

func helper() {}

type User struct {
    Name string
    Age  int
}

type Repository interface {
    Find(id string) User
}
""")


def test_go_imports():
    r = _make_result(GO_CODE, "go")
    names = {i.variable_name for i in r["imports"]}
    assert names == {"fmt", "http"}


def test_go_functions():
    r = _make_result(GO_CODE, "go")
    funcs = {(f.name, f.is_exported) for f in r["functions"]}
    assert ("Login", True) in funcs
    assert ("helper", False) in funcs


def test_go_classes():
    r = _make_result(GO_CODE, "go")
    class_names = {c.name for c in r["classes"]}
    assert "User" in class_names
    assert "Repository" in class_names


def test_go_exports():
    r = _make_result(GO_CODE, "go")
    exp_names = {e.variable_name for e in r["exports"]}
    assert "Login" in exp_names
    assert "User" in exp_names
    assert "helper" not in exp_names


def test_go_calls():
    r = _make_result(GO_CODE, "go")
    callee_names = {c.callee_name for c in r["calls"]}
    assert "fmt.Println" in callee_names


# ── Java ──────────────────────────────────────

JAVA_CODE = textwrap.dedent("""\
package com.example;
import java.util.List;
import static org.junit.Assert.*;

public class UserService {
    public User findById(Long id) {
        return null;
    }
    private void helper() {}
}

class PackagePrivate {}
""")


def test_java_imports():
    r = _make_result(JAVA_CODE, "java")
    sources = {i.source_module for i in r["imports"]}
    assert "java.util.List" in sources
    assert "org.junit.Assert.*" in sources


def test_java_functions():
    r = _make_result(JAVA_CODE, "java")
    funcs = {(f.name, f.is_exported) for f in r["functions"]}
    assert ("findById", True) in funcs
    assert ("helper", True) in funcs  # public in pattern match


def test_java_classes():
    r = _make_result(JAVA_CODE, "java")
    names = {c.name for c in r["classes"]}
    assert "UserService" in names
    assert "PackagePrivate" in names


def test_java_exports():
    r = _make_result(JAVA_CODE, "java")
    exp_names = {e.variable_name for e in r["exports"]}
    assert "findById" in exp_names
    assert "UserService" in exp_names


# ── C ─────────────────────────────────────────

C_CODE = textwrap.dedent("""\
#include <stdio.h>
#include "local.h"

int main(int argc, char *argv[]) {
    printf("hello");
    return 0;
}

struct Point {
    int x;
    int y;
};

enum Color { RED, GREEN, BLUE };
""")


def test_c_imports():
    r = _make_result(C_CODE, "c")
    names = {i.variable_name for i in r["imports"]}
    assert "stdio" in names


def test_c_functions():
    r = _make_result(C_CODE, "c")
    func_names = {f.name for f in r["functions"]}
    assert "main" in func_names


def test_c_classes():
    r = _make_result(C_CODE, "c")
    names = {c.name for c in r["classes"]}
    assert "Point" in names
    assert "Color" in names
    # No duplicates
    assert len(r["classes"]) == 2


# ── C++ ───────────────────────────────────────

CPP_CODE = textwrap.dedent("""\
#include <iostream>
#include <vector>
using namespace std;

class MyClass {
public:
    void doSomething(int x);
private:
    int helper();
};
""")


def test_cpp_imports():
    r = _make_result(CPP_CODE, "cpp")
    names = {i.variable_name for i in r["imports"]}
    assert "iostream" in names
    assert "vector" in names


def test_cpp_functions():
    r = _make_result(CPP_CODE, "cpp")
    func_names = {f.name for f in r["functions"]}
    assert "doSomething" in func_names
    assert "helper" in func_names


def test_cpp_classes():
    r = _make_result(CPP_CODE, "cpp")
    names = {c.name for c in r["classes"]}
    assert "MyClass" in names


# ── C# ────────────────────────────────────────

CS_CODE = textwrap.dedent("""\
using System;
using System.Collections.Generic;

public class UserService {
    public User GetUser(int id) {
        return null;
    }
    private void Log(string msg) {}
}

public struct Point {
    public int X, Y;
}
""")


def test_cs_imports():
    r = _make_result(CS_CODE, "csharp")
    names = {i.variable_name for i in r["imports"]}
    assert "System" in names


def test_cs_functions():
    r = _make_result(CS_CODE, "csharp")
    func_names = {f.name for f in r["functions"]}
    assert "GetUser" in func_names
    assert "Log" in func_names


def test_cs_classes():
    r = _make_result(CS_CODE, "csharp")
    names = {c.name for c in r["classes"]}
    assert "UserService" in names
    assert "Point" in names


# ── Rust ──────────────────────────────────────

RUST_CODE = textwrap.dedent("""\
use std::collections::HashMap;
use crate::models::User;

pub fn login(user: &str, pass: &str) -> Result<bool, Error> {
    Ok(true)
}

fn helper() -> i32 { 42 }

pub struct User {
    pub name: String,
    age: i32,
}

pub trait Authenticator {
    fn authenticate(&self) -> bool;
}

mod utils;
""")


def test_rust_imports():
    r = _make_result(RUST_CODE, "rust")
    names = {i.variable_name for i in r["imports"]}
    assert "HashMap" in names
    assert "User" in names
    assert "utils" in names


def test_rust_functions():
    r = _make_result(RUST_CODE, "rust")
    funcs = {(f.name, f.is_exported) for f in r["functions"]}
    assert ("login", True) in funcs
    assert ("helper", False) in funcs


def test_rust_classes():
    r = _make_result(RUST_CODE, "rust")
    names = {c.name for c in r["classes"]}
    assert "User" in names
    assert "Authenticator" in names


def test_rust_exports():
    r = _make_result(RUST_CODE, "rust")
    exp_names = {e.variable_name for e in r["exports"]}
    assert "login" in exp_names
    assert "User" in exp_names
    assert "helper" not in exp_names


# ── Ruby ──────────────────────────────────────

RUBY_CODE = textwrap.dedent("""\
require 'json'
require_relative './helper'
include Enumerable

def login(user, pass)
  true
end

class User
  def name
    @name
  end
end

module Helpers
  def format_date(date)
  end
end
""")


def test_ruby_imports():
    r = _make_result(RUBY_CODE, "ruby")
    sources = {i.source_module for i in r["imports"]}
    assert "json" in sources
    assert "Enumerable" in sources


def test_ruby_functions():
    r = _make_result(RUBY_CODE, "ruby")
    func_names = {f.name for f in r["functions"]}
    assert "login" in func_names
    assert "name" in func_names
    assert "format_date" in func_names


def test_ruby_classes():
    r = _make_result(RUBY_CODE, "ruby")
    names = {c.name for c in r["classes"]}
    assert "User" in names
    assert "Helpers" in names


def test_ruby_exports():
    r = _make_result(RUBY_CODE, "ruby")
    exp_names = {e.variable_name for e in r["exports"]}
    assert "login" in exp_names
    assert "User" in exp_names


# ── Swift ─────────────────────────────────────

SWIFT_CODE = textwrap.dedent("""\
import Foundation
import UIKit

public func login(user: String, password: String) -> Bool {
    return true
}

private func helper() {}

public class UserService {
    public func fetchUser(id: Int) -> User? { nil }
}

struct InternalModel {
    var name: String
}
""")


def test_swift_imports():
    r = _make_result(SWIFT_CODE, "swift")
    names = {i.variable_name for i in r["imports"]}
    assert "Foundation" in names
    assert "UIKit" in names


def test_swift_functions():
    r = _make_result(SWIFT_CODE, "swift")
    func_names = {f.name for f in r["functions"]}
    assert "login" in func_names
    assert "helper" in func_names
    assert "fetchUser" in func_names


def test_swift_classes():
    r = _make_result(SWIFT_CODE, "swift")
    names = {c.name for c in r["classes"]}
    assert "UserService" in names
    assert "InternalModel" in names


def test_swift_exports():
    r = _make_result(SWIFT_CODE, "swift")
    exp_names = {e.variable_name for e in r["exports"]}
    assert "login" in exp_names
    assert "UserService" in exp_names


# ── Kotlin ────────────────────────────────────

KOTLIN_CODE = textwrap.dedent("""\
package com.example
import kotlinx.coroutines.*
import com.example.models.User

fun login(user: String, password: String): Boolean {
    return true
}

class UserService {
    fun findById(id: Long): User? = null
}

data class UserData(val id: Long, val name: String)
object AppConfig {
    val version = "1.0"
}
""")


def test_kotlin_imports():
    r = _make_result(KOTLIN_CODE, "kotlin")
    sources = {i.source_module for i in r["imports"]}
    assert "kotlinx.coroutines.*" in sources
    assert "com.example.models.User" in sources


def test_kotlin_functions():
    r = _make_result(KOTLIN_CODE, "kotlin")
    func_names = {f.name for f in r["functions"]}
    assert "login" in func_names
    assert "findById" in func_names


def test_kotlin_classes():
    r = _make_result(KOTLIN_CODE, "kotlin")
    names = {c.name for c in r["classes"]}
    assert "UserService" in names
    assert "UserData" in names
    assert "AppConfig" in names


# ── Vue ───────────────────────────────────────

VUE_CODE = textwrap.dedent("""\
<template>
  <div>{{ msg }}</div>
</template>
<script setup>
import { ref, computed } from 'vue';
import UserCard from './UserCard.vue';

const msg = ref('hello');

export function greet(name: string): string {
  return 'Hi ' + name;
}
</script>
""")


def test_vue_imports():
    r = _make_result(VUE_CODE, "vue")
    names = {i.variable_name for i in r["imports"]}
    assert "ref" in names
    assert "computed" in names


def test_vue_functions():
    r = _make_result(VUE_CODE, "vue")
    func_names = {f.name for f in r["functions"]}
    assert "greet" in func_names


def test_vue_exports():
    r = _make_result(VUE_CODE, "vue")
    exp_names = {e.variable_name for e in r["exports"]}
    assert "greet" in exp_names


# ── Svelte ────────────────────────────────────

SVELTE_CODE = """<script>
  import { writable } from 'svelte/store';
  export let name = 'world';
  function greet() { return 'hello'; }
</script>
<h1>Hello {name}!</h1>
"""


def test_svelte_imports():
    r = _make_result(SVELTE_CODE, "svelte")
    names = {i.variable_name for i in r["imports"]}
    assert "writable" in names


def test_svelte_functions():
    r = _make_result(SVELTE_CODE, "svelte")
    func_names = {f.name for f in r["functions"]}
    assert "greet" in func_names


# ── Bash ──────────────────────────────────────

BASH_CODE = textwrap.dedent("""\
#!/bin/bash
source ./lib.sh
. ./config.sh

function deploy() {
    echo "deploying"
}

build() {
    echo "building"
}

if [ "$1" = "test" ]; then
    deploy
fi
""")


def test_bash_imports():
    r = _make_result(BASH_CODE, "bash")
    sources = {i.source_module for i in r["imports"]}
    assert "./lib.sh" in sources
    assert "./config.sh" in sources


def test_bash_functions():
    r = _make_result(BASH_CODE, "bash")
    func_names = {f.name for f in r["functions"]}
    assert "deploy" in func_names
    assert "build" in func_names
    # "if" should NOT be captured as a function
    assert "if" not in func_names


# ── Edge cases ────────────────────────────────

def test_empty_file_returns_empty():
    for lang in ["go", "java", "c", "cpp", "csharp", "rust", "ruby", "swift", "kotlin", "bash"]:
        r = _make_result("", lang)
        assert r["imports"] == [] or len(r["imports"]) == 0
        assert r["functions"] == [] or len(r["functions"]) == 0


def test_strip_comments_removes_single_line():
    result = parser._strip_comments("// this is a comment\nint x = 1;")
    assert "comment" not in result
    assert "int x = 1" in result


def test_strip_comments_removes_block():
    result = parser._strip_comments("/* block\ncomment */\nint x = 1;")
    assert "block" not in result
    assert "int x = 1" in result


def test_generic_calls_filters_keywords():
    code = "if (x) { return foo(y); }"
    calls = parser._extract_generic_calls(code, frozenset({"if", "return"}))
    callee_names = {c.callee_name for c in calls}
    assert "if" not in callee_names
    assert "return" not in callee_names
    # "foo" should be captured
    assert "foo" in callee_names
