# Qoder Token 用量插件 — 构建脚本

.PHONY: pack pack-open install clean test

# 默认目标：打包
pack:
	python3 skills/token-usage/scripts/package.py

# 打包并打开 dist 目录
pack-open:
	python3 skills/token-usage/scripts/package.py --open

# 安装到本地插件目录
install: pack
	@echo "安装到本地插件目录..."
	@VERSION=$$(python3 -c "import json; print(json.load(open('.qoder-plugin/plugin.json'))['version'])"); \
	mkdir -p ~/.qoder/plugins/cache/local/token-usage/$$VERSION; \
	rsync -av --delete .qoder-plugin/ ~/.qoder/plugins/cache/local/token-usage/$$VERSION/.qoder-plugin/; \
	rsync -av --delete skills/ ~/.qoder/plugins/cache/local/token-usage/$$VERSION/skills/; \
	rsync -av --delete commands/ ~/.qoder/plugins/cache/local/token-usage/$$VERSION/commands/; \
	rsync -av --delete assets/ ~/.qoder/plugins/cache/local/token-usage/$$VERSION/assets/; \
	cp README.md CHANGELOG.md LICENSE ~/.qoder/plugins/cache/local/token-usage/$$VERSION/ 2>/dev/null || true; \
	echo "安装完成：~/.qoder/plugins/cache/local/token-usage/$$VERSION/"

# 清理临时文件
clean:
	find . -name ".DS_Store" -delete 2>/dev/null || true
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f skills/token-usage/pricing.json.bak-* 2>/dev/null || true
	rm -f skills/token-usage/.pricing-update-state.json 2>/dev/null || true

# 运行测试
test:
	python3 skills/token-usage/scripts/usage_report.py --days 7
	python3 skills/token-usage/scripts/usage_report.py --days all --by model --json | head -5
	python3 skills/token-usage/scripts/build_dashboard.py
	python3 skills/token-usage/scripts/build_canvas.py --workspace "$$(pwd)"

# 完整发布流程：清理 → 测试 → 打包 → 安装
release: clean test pack install
	@echo ""
	@echo "=== 发布完成 ==="
	@VERSION=$$(python3 -c "import json; print(json.load(open('.qoder-plugin/plugin.json'))['version'])"); \
	echo "版本：$$VERSION"; \
	echo "包文件：dist/token-usage-$$VERSION.zip"; \
	echo "本地安装：~/.qoder/plugins/cache/local/token-usage/$$VERSION/"
