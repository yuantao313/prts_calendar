// PRTS 日历 — Jenkins Pipeline（由 .github/workflows/update-calendar.yml 迁移而来）
//
// 前置要求：
//   1. Jenkins agent 需安装 python3、pip、git 以及 GitHub CLI（gh）
//   2. Jenkins 凭证 github-pat：Secret text，值为 GitHub PAT（classic 需 repo 权限；
//      fine-grained 需 Contents 读写，且授权本仓库）
//   3. 定时触发：每小时第 30 分钟（与原 cron "30 * * * *" 一致）；如需 push 触发，
//      可在 GitHub 仓库配置 Jenkins 的 Webhook（注意：仓库 Actions 已全局禁用）
pipeline {
    agent any

    triggers {
        cron('30 * * * *')
    }

    environment {
        GH_TOKEN = credentials('github-pat')   // gh CLI 上传 Release 用
        REPO     = 'yuantao313/prts_calendar'
        GIT_URL  = 'https://github.com/yuantao313/prts_calendar.git'
    }

    stages {
        stage('生成 ICS') {
            steps {
                sh '''
                    set -e
                    command -v python3 >/dev/null || { echo "缺少 python3，请先在 Jenkins agent 安装"; exit 1; }
                    python3 --version
                    pip install -q -r requirements.txt
                    python3 prts_calendar.py --mode all
                '''
            }
        }

        stage('拆分输出') {
            steps {
                sh '''
                    set -e
                    rm -rf output_archive output_latest
                    mkdir -p output_archive output_latest
                    # 每年归档：仅 *_YYYY.ics（不要 _latest / _all）
                    for f in output/*.ics; do
                        case "$f" in
                            *'_latest.ics'|*'_all.ics') ;;
                            *) cp "$f" output_archive/ ;;
                        esac
                    done
                    # 当年+全量：仅 _latest 与 _all
                    cp output/*_latest.ics output/*_all.ics output_latest/
                    echo "归档文件数: $(ls output_archive/*.ics 2>/dev/null | wc -l)"
                    echo "latest 文件数: $(ls output_latest/*.ics 2>/dev/null | wc -l)"
                '''
            }
        }

        stage('上传 Release') {
            steps {
                sh '''
                    set -e
                    command -v gh >/dev/null || { echo "缺少 gh CLI，请先在 Jenkins agent 安装"; exit 1; }

                    # Release「每年归档」- 删除旧资源并补传（保持非 Latest）
                    if gh release view archive --repo "$REPO" &>/dev/null; then
                        for name in $(gh release view archive --repo "$REPO" --json assets -q '.assets[].name'); do
                            gh release delete-asset archive "$name" --repo "$REPO" --yes
                        done
                    fi
                    # 已存在则跳过创建，统一走下方 --clobber 补传
                    gh release create archive --repo "$REPO" --title "每年归档" \
                        --notes "按年份归档的卡池与活动 ICS，可按年下载。" \
                        --target "${GIT_COMMIT}" 2>/dev/null || true
                    for f in output_archive/*.ics; do
                        gh release upload archive "$f" --repo "$REPO" --clobber
                    done

                    # Release「当年+全量」- 设为仓库 Latest
                    if gh release view latest --repo "$REPO" &>/dev/null; then
                        for name in $(gh release view latest --repo "$REPO" --json assets -q '.assets[].name'); do
                            gh release delete-asset latest "$name" --repo "$REPO" --yes
                        done
                    fi
                    gh release create latest --repo "$REPO" --title "当年 + 全量" \
                        --notes "当年订阅用 *_latest.ics，全量 *_all.ics，可导入或订阅。" \
                        --target "${GIT_COMMIT}" 2>/dev/null || true
                    for f in output_latest/*.ics; do
                        gh release upload latest "$f" --repo "$REPO" --clobber
                    done
                '''
            }
        }

        stage('Keep alive') {
            steps {
                sh '''
                    set -e
                    # 记录当前分支，结束后恢复，避免污染下次构建的工作区
                    ORIG_BRANCH=$(git rev-parse --abbrev-ref HEAD)
                    git config user.name "jenkins[bot]"
                    git config user.email "jenkins[bot]@users.noreply.github.com"
                    git checkout --orphan live-heartbeat
                    git rm -rf . >/dev/null 2>&1 || true
                    date > .heartbeat
                    git add .heartbeat
                    git commit -m "heartbeat $(date -u +%Y-%m-%dT%H:%M:%SZ)"
                    git push "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git" live-heartbeat:live --force
                    git checkout -f "$ORIG_BRANCH"
                    git clean -fdx
                '''
            }
        }
    }

    post {
        success {
            echo "PRTS 日历构建完成：ICS 已生成并上传至 archive / latest Release"
        }
        failure {
            echo "PRTS 日历构建失败，请查看控制台日志"
        }
    }
}
