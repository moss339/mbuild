# moss-build

MOSS 通用构建系统 - Python CLI 工具

## 功能特性

- **YAML 配置驱动** - 通过 `moss.yaml` 定义构建目标，含 Git 仓库信息
- **自动依赖解析** - 拓扑排序确定构建顺序
- **并行构建** - 支持 `-j N` 并行编译
- **自动源码同步** - 按 YAML 定义自动 clone/update Git 仓库
- **标准化安装** - `install` 命令输出标准化部署产物

## 安装

```bash
pip install -e .
# 或
pip install moss-build
```

## 快速开始

```bash
# 验证配置
moss-build validate -c moss.yaml

# 列出组件
moss-build list -c moss.yaml

# 同步源码
moss-build sync -c moss.yaml

# 构建全部
moss-build build -c moss.yaml -j 4

# 安装到 dist/
moss-build install -c moss.yaml

# 查看依赖关系
moss-build deps -c moss.yaml

# 清理构建产物
moss-build clean
```

## 配置示例 `moss.yaml`

```yaml
name: moss-full
settings:
  build_root: ./build
  install_root: ./dist
  cache_dir: .moss/cache
  parallel_jobs: 8
  build_type: Release

components:
  - name: mshm
    repository:
      url: https://github.com/moss339/mshm.git
      branch: main
    local_path: mshm
    build:
      type: library
      language: C

  - name: mdds
    repository:
      url: https://github.com/moss339/mdds.git
      branch: main
    local_path: mdds
    dependencies:
      - name: mshm
        local_path: mshm
    build:
      type: library
      language: C++17

  - name: mcom
    repository:
      url: https://github.com/moss339/mcom.git
      branch: main
    local_path: mcom
    dependencies:
      - name: mdds
        local_path: mdds
      - name: mshm
        local_path: mshm
    build:
      type: library
      language: C++17
```

## 命令

| 命令 | 说明 |
|------|------|
| `build` | 按拓扑顺序构建所有组件 |
| `sync` | 同步（克隆/更新）所有组件源码 |
| `install` | 安装到指定目录 |
| `list` | 列出所有组件 |
| `deps` | 显示依赖关系图 |
| `validate` | 验证 YAML 配置 |
| `clean` | 清理构建产物 |

## License

MIT
