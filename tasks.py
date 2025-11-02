import os
import subprocess

def run(cmd):
    print(f"▶ {cmd}")
    subprocess.run(cmd, shell=True, check=False)

def review():
    run("pre-commit run --all-files")
    run("black backend")
    run("flake8 backend")
    run("mypy backend")
    run("bandit -r backend")
    run("safety check")
    run("cd gateway && npx eslint .")
    run("cd frontend && npx eslint .")

def perf():
    run("python devops/audits/locustfile.py")

def rag_eval():
    run("python devops/audits/rag_eval.py")

def test():
    run("pytest -q")

# default action
if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "review"
    globals().get(target, review)()
