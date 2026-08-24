// PRTS 日历 — Jenkins Pipeline（由 .github/workflows/update-calendar.yml 迁移而来）
//
// 前置要求：
//   1. Jenkins agent 需安装 python3、pip
//   2. 定时触发：每小时第 30 分钟（与原 cron "30 * * * *" 一致）；如需 push 触发，
//      可在 GitHub 仓库配置 Jenkins 的 Webhook（注意：仓库 Actions 已全局禁用）
//   产物：ICS 作为 Jenkins 构建产物归档，不再上传 GitHub Release
pipeline {
    agent any

    triggers {
        cron('30 * * * *')
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

        stage('归档产物') {
            steps {
                // ICS 作为 Jenkins 构建产物归档，可从任务页下载（不再上传 GitHub Release）
                archiveArtifacts artifacts: 'output_archive/**/*.ics, output_latest/**/*.ics',
                                 fingerprint: true,
                                 allowEmptyArchive: false
            }
        }

    }

    post {
        success {
            echo "PRTS 日历构建完成：ICS 已归档为 Jenkins 构建产物"
        }
        failure {
            echo "PRTS 日历构建失败，请查看控制台日志"
        }
    }
}
