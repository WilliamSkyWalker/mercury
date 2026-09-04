#!/bin/bash
# 打tag脚本
#set -x
export LANG="en_US.UTF-8"
function error_exit() {
  exit 1
}
# read -r -p "输入分支名 [dev/test/uat/prd] " branch

read -r -p "输入tags，规则为：分支-日期-序号，例如： [prod-20231101-v1] " version
echo 'version: ' $version
version_check=$(echo $version | grep -o '202' | wc -l)
if [[ $version_check -le 0 ]] || [[ "$version" =~ ^202.* ]];then
    echo "你的tags，输入有误，请遵循以下规则："
    echo "dev、test环境允许非dev分支发布，规则为：分支-日期-序号，例如： [prod-20231101-v1]"
    echo "完整发布流程[要发布到uat|sd|prod]，固定用dev分支开头，规则为：dev-日期-序号，例如： [dev-20231101-v1]"
    error_exit
fi
read -r -p "输入commit，例如： [update deploy.sh] " commit
echo 'commit: ' $commit

git add -A ./
git add -A ./.gitlab-ci.yml
git commit -m "${commit}"
git push

git tag -a $version -m "${commit}"
git push origin $version
