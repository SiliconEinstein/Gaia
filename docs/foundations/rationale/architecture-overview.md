# 架构概述

> **Status:** Current canonical

Gaia 的架构围绕一个三层编译管线和两个共享公共中间表示的产品表面来组织。

## 三层管线

```
Gaia Lang (authored surface)
    |
    v  gaia build (deterministic compilation)
Gaia IR (structural factor graph)
    |
    v  gaia infer / server BP
Belief Propagation (probabilistic inference)
```

每层都有清晰的边界：

1. **Gaia Lang**——编写表面。一种基于 Typst 的 DSL，用于声明知识对象、推理链和包结构。确定性地编译为 Gaia IR。参见 `../gaia-lang/spec.md`。

2. **Gaia IR**——结构中间表示。一个包含 knowledge node（知识节点，变量）和 factor node（因子节点，约束）的二部因子图。Gaia IR 是**提交制品**——CLI 与 LKM 之间的合约。参见 `../gaia-ir/overview.md`。

3. **Belief Propagation**——在 Gaia IR 上的概率推理。根据先验和因子势函数计算所有知识节点的后验信念。参见 `../bp/inference.md`。

## 两个产品表面

Gaia IR 是 Gaia 两个产品表面之间的边界：

| | CLI | LKM（服务器） |
|---|---|---|
| **范围** | 本地，单个包 | 全局，多包 |
| **输入** | Gaia Lang 源文件（.typ 文件） | 已发布的 Gaia IR |
| **编译** | Gaia Lang -> Gaia IR | 不适用——接收 Gaia IR |
| **推理** | 在本地规范图上运行本地 BP | 在全局规范图上运行全局 BP |
| **存储** | LanceDB + Kuzu（嵌入式） | LanceDB + Neo4j + 向量 |
| **额外服务** | — | 审查、策展、全局规范化 |

CLI 是 Gaia IR 的**前端**——类比于 Clang 是 LLVM IR 的前端。LKM 永远不会看到 Gaia Lang；它纯粹在 Gaia IR 上操作。

## 为什么采用这种分解

**Gaia IR 作为共享合约提供：**

- **可审计的降级**——从编写源到因子图的映射是显式且确定性的
- **前端独立性**——未来的前端可以在不使用 Typst 的情况下生成 Gaia IR
- **CLI 与 LKM 解耦**——LKM 在 Gaia IR 上进行验证和操作，独立于编写表面
- **结构与参数分离**——Gaia IR 仅携带结构；概率存在于参数化覆盖层中

**Gaia Lang 作为 CLI 专用前端是因为：**

- 语言是编写关注点，而非推理关注点
- LKM 接收编译后的制品，而非源代码
- 语言的演进不影响 LKM 的合约

## 类比

| Gaia | 编译器生态系统 | 角色 |
|---|---|---|
| Gaia Lang | Rust / C++ / Swift 源代码 | 编写表面 |
| Gaia IR | LLVM IR / MIR / SIL | 共享中间表示 |
| BP | LLVM codegen / 执行 | 在 IR 上的计算 |
| CLI | cargo / clang / swift build | 本地工具（本地编译 + 运行） |
| LKM | crates.io / PyPI / npm registry | 包注册中心 + 计算后端 |

## 参考文献

- `docs/foundations/rationale/product-scope.md`——产品定位
- `docs/foundations/theory/01-plausible-reasoning.md`——理论基础
