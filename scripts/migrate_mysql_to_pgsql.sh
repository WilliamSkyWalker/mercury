#!/bin/bash
# MySQL → PostgreSQL 数据迁移脚本
# 用法: bash scripts/migrate_mysql_to_pgsql.sh
#
# 前置条件:
#   1. MySQL 和 PostgreSQL 都在运行
#   2. PostgreSQL 中已创建 mercury 数据库: createdb -U postgres mercury
#   3. 已安装 pgloader: brew install pgloader (macOS) / apt install pgloader (Ubuntu)
#
# 迁移策略: 使用 pgloader 直接从 MySQL 迁移到 PostgreSQL

set -e

# ============ 配置区 ============
# MySQL
MYSQL_HOST="127.0.0.1"
MYSQL_PORT=3306
MYSQL_USER="root"
MYSQL_PASS="123456"
MYSQL_DB="mercury"

# PostgreSQL
PG_HOST="127.0.0.1"
PG_PORT=5432
PG_USER="postgres"
PG_PASS="123456"
PG_DB="mercury"
# ================================

echo "=============================="
echo " MySQL → PostgreSQL 迁移"
echo "=============================="

# 检查 pgloader 是否安装
if ! command -v pgloader &> /dev/null; then
    echo "❌ pgloader 未安装"
    echo "   macOS:  brew install pgloader"
    echo "   Ubuntu: sudo apt install pgloader"
    exit 1
fi

# 方式一: 使用 pgloader 自动迁移（推荐）
echo ""
echo ">>> 方式一: pgloader 自动迁移"
echo ""

PGLOADER_CMD=$(cat <<EOF
LOAD DATABASE
    FROM mysql://${MYSQL_USER}:${MYSQL_PASS}@${MYSQL_HOST}:${MYSQL_PORT}/${MYSQL_DB}
    INTO postgresql://${PG_USER}:${PG_PASS}@${PG_HOST}:${PG_PORT}/${PG_DB}

WITH include drop, create tables, create indexes, reset sequences,
     workers = 4, concurrency = 1

SET maintenance_work_mem to '128MB',
    work_mem to '12MB'

-- 类型映射
CAST type int to integer,
     type bigint to bigint,
     type tinyint to boolean using tinyint-to-boolean,
     type varchar to varchar,
     type text to text,
     type longtext to text,
     type json to jsonb,
     type datetime to timestamptz,
     type float to double precision,
     type double to double precision

-- 只迁移 ceres_ 开头的表
INCLUDING ONLY TABLE NAMES MATCHING ~/ceres_.*/

BEFORE LOAD DO
\$\$ DROP SCHEMA IF EXISTS ${MYSQL_DB} CASCADE; \$\$

AFTER LOAD DO
\$\$ ALTER SCHEMA ${MYSQL_DB} RENAME TO public; \$\$;
EOF
)

echo "$PGLOADER_CMD" > /tmp/mercury_pgloader.conf
echo "pgloader 配置已写入 /tmp/mercury_pgloader.conf"
echo ""
echo "执行迁移:"
echo "  pgloader /tmp/mercury_pgloader.conf"
echo ""

# 方式二: 使用 Django dumpdata/loaddata（备选，更安全）
echo ">>> 方式二: Django dumpdata/loaddata（备选）"
echo ""
echo "步骤:"
echo "  1. 确保 settings.py 仍连接 MySQL"
echo "  2. 导出数据:"
echo "     python3 manage.py dumpdata ceres --indent 2 -o scripts/ceres_data.json"
echo "  3. 修改 settings.py 连接 PostgreSQL"
echo "  4. 建表:"
echo "     python3 manage.py migrate"
echo "  5. 导入数据:"
echo "     python3 manage.py loaddata scripts/ceres_data.json"
echo ""

read -p "选择迁移方式 (1=pgloader / 2=django dumpdata / q=退出): " choice

case $choice in
    1)
        echo "正在执行 pgloader 迁移..."
        pgloader /tmp/mercury_pgloader.conf
        echo ""
        echo "✅ pgloader 迁移完成"
        echo ""
        echo "接下来请:"
        echo "  1. 确认 settings.py 已切换到 PostgreSQL"
        echo "  2. 运行 python3 manage.py migrate --fake 标记已有迁移"
        echo "  3. 验证: python3 manage.py dbshell 后执行 \\dt 查看表"
        ;;
    2)
        echo "请按上述步骤手动执行 Django dumpdata/loaddata"
        ;;
    q|Q)
        echo "退出"
        exit 0
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac
