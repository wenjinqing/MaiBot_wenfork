#!/bin/bash
# ============================================================
# 紧急删除敏感文件脚本
# ============================================================
# 警告：此脚本会重写 Git 历史，使用前请确保：
# 1. 已经备份了重要数据
# 2. 确认要删除的文件路径
# 3. 通知所有协作者重新克隆仓库
# ============================================================

echo "⚠️  警告：此操作将重写 Git 历史！"
echo "请确保你已经："
echo "1. 备份了重要数据"
echo "2. 确认要删除的文件"
echo "3. 准备好强制推送到远程仓库"
echo ""
read -p "确认继续？(输入 YES 继续): " confirm

if [ "$confirm" != "YES" ]; then
    echo "操作已取消"
    exit 1
fi

echo ""
echo "开始清理敏感文件..."
echo ""

# 要删除的敏感文件列表
SENSITIVE_FILES=(
    ".env"
    "config/bot_config.toml"
    "config/yiyi_bot_config.toml"
    "*.db"
    "*.sqlite"
)

# 从 Git 历史中删除每个文件
for file in "${SENSITIVE_FILES[@]}"; do
    echo "正在删除: $file"
    git filter-branch --force --index-filter \
        "git rm --cached --ignore-unmatch '$file'" \
        --prune-empty --tag-name-filter cat -- --all
done

echo ""
echo "✅ 本地历史已清理完成"
echo ""
echo "下一步操作："
echo "1. 立即更换所有泄露的密钥/密码/Token"
echo "2. 运行以下命令强制推送到远程："
echo "   git push origin --force --all"
echo "   git push origin --force --tags"
echo ""
echo "3. 通知所有协作者："
echo "   - 删除本地仓库"
echo "   - 重新克隆仓库"
echo ""
read -p "是否现在强制推送到远程？(输入 YES 继续): " push_confirm

if [ "$push_confirm" = "YES" ]; then
    echo "正在强制推送..."
    git push origin --force --all
    git push origin --force --tags
    echo "✅ 推送完成"
else
    echo "跳过推送，你可以稍后手动执行："
    echo "git push origin --force --all"
fi

echo ""
echo "⚠️  重要提醒："
echo "1. 立即更换所有可能泄露的密钥"
echo "2. 检查 GitHub 的 commit 历史确认文件已删除"
echo "3. 考虑将仓库设为私有"
