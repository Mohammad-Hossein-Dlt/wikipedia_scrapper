import os
import re
import shutil
import subprocess
import importlib.util
from pathlib import Path
from typing import Iterable
import json

# Python 3.11+ has tomllib in stdlib. For 3.10- fallback to 'tomli' if installed.
try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:
        tomllib = None  # we'll guard its usage

exclusive_packages = {
    "fastapi",
    "pydantic",
    "pymongo",
    "motor",
}

mirror = [
    "--index",
    # "https://mirror-pypi.runflare.com/simple",
    # "https://package-mirror.liara.ir/repository/pypi",
    "https://repo.hmirror.ir/python/simple",
]

base_env = {
    "UV_MANAGED": "false",
    "UV_NO_SYNC_VENV": "true",
    "PYTHONUTF8": "1",
}

def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    return_result: bool = False,
) -> str:

    env = os.environ.copy()
    env.update(base_env)
    
    print()
    print(' '.join(cmd))
    print()
    
    if return_result:

        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
        )
        
        if proc.returncode != 0:
            print(proc.stderr.strip())
                
        return proc.stdout
    else:
        subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            shell=True,
        )

def name_only(
    name: str,
) -> str:
    
    name = name.strip()
    name = re.split(r";", name, maxsplit=1)[0]
    name = re.split(r"\[", name, maxsplit=1)[0]
    name = re.split(r"[<>=!~ ]", name, maxsplit=1)[0]
    result = name.replace("_", "-").lower()
    
    return result

def parse_pyproject_dependencies(
    pyproject_path: Path,
) -> set[str]:
    
    if not pyproject_path.exists():
        return set()
    if tomllib is None:
        return set()

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    deps = [d.strip() for d in data.get("project", {}).get("dependencies", [])]
    return {name_only(d) for d in deps}


def parse_requirements_names(
    req_path: Path,
) -> set[str]:
    
    if not req_path.exists():
        return set()
    names: set[str] = set()
    for line in req_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        names.add(name_only(line))
    return names

def discover_dirs(
    root: Path,
) -> Iterable[Path]:
    
    yield root
        
    for child in root.iterdir():
        if child.is_dir() and (child / "src").is_dir():
            yield child
    

def ensure_uv_available() -> None:
    if shutil.which("uv") is None:
        raise RuntimeError("Uv is not installed.")
    
def ensure_venv_available(
    dir: Path,
) -> None:
    
    venv = dir / ".venv"
    
    if venv.exists():
        print("venv exists, Run 'uv sync'")
        run_cmd(
            [
                "uv",
                "sync",
                *mirror,
            ],
        )
    else:
        print("venv not exists, Run 'uv venv'")
        run_cmd(
            cmd=[
                "uv",
                "venv"
            ],
            cwd=dir,
        )
        ensure_venv_available(dir)
    
def ensure_pyproject(
    dir: Path,
) -> None:

    run_cmd(
        cmd=[
            "uv",
            "init",
            "--bare",  
        ],
        cwd=dir,
    )
    
def check_requirements(
    dir: Path,
):
    installed = importlib.util.find_spec("pipdeptree") is not None
    ensure_pyproject(dir)
    if not installed:
        print("pipdeptree is not installed, Installing pipdeptree...")
        run_cmd(
            cmd=[
                "uv",
                "add",
                "pipdeptree",
                *mirror,
                "--active",
            ],
            cwd=dir,
        )
    
def get_top_packages(dir: Path):
    
    requirements = ""
        
    result = run_cmd(
        cmd=[
            "uv",
            "run",
            "pipdeptree",
            "--json",
        ],
        cwd=dir,
        return_result=True,
    )
    data: list[dict] = json.loads(result)
    
    deps = set()
    top_pkgs = set()
    top_pkgs_with_version = dict()
    for pkg in data:
                    
        top_pkgs.add(pkg["package"]["package_name"])
        top_pkgs_with_version[pkg["package"]["package_name"]] =  pkg["package"]["installed_version"]
        for depend in pkg.get("dependencies", []):
            deps.add(depend["package_name"])        
        
    top_pkgs = top_pkgs - (deps - exclusive_packages)
    top_pkgs = sorted(top_pkgs)
    for k, v in top_pkgs_with_version.items():
        for p in top_pkgs:
            if p == k:
                requirements += f"{p}>={v}" + "\n"
                    
    return requirements

def process(
    dir: Path,
) -> None:
        
    pyproject = dir / "pyproject.toml"
    requirements = dir / "requirements.txt"
    
    ensure_pyproject(dir)
        
    requirements.write_text(
        get_top_packages(dir),
        encoding="utf-8",
    )

    deps_set = parse_pyproject_dependencies(pyproject)
    req_names = parse_requirements_names(requirements)
    to_remove = sorted(deps_set - req_names)

    if to_remove:
        print(f"Pruning from pyproject.toml: {' '.join(to_remove)}")
        run_cmd(
            cmd=[
                "uv",
                "remove",
                *to_remove,
                "--active",
            ],
            cwd=dir,
        )
    else:
        print("No package to prune from pyproject.toml.")

    run_cmd(
        cmd=[
            "uv",
            "add",
            "-r",
            "requirements.txt",
            *mirror,
            "--active",
            # "--no-sync",
            "--frozen",
        ],
        cwd=dir,
    )

    print(f"Process done in {dir.name}")
    
def remove_uv_lock(
    dir: Path,
) -> None:
    uv_lock = dir / "uv.lock"
    
    if uv_lock.exists():
        try:
            uv_lock.unlink()
        except OSError:
            # If file is locked
            uv_lock.chmod(0o666)
            uv_lock.unlink(missing_ok=True)
            
    print(f"uv.lock removed in {dir.name}")
            
def main() -> None:

    ensure_uv_available()
    ensure_venv_available(Path.cwd())
    check_requirements(Path.cwd())

    paths_list = list(discover_dirs(Path.cwd()))

    if not paths_list:
        return

    for path in paths_list:
        try:
            print(path)
            process(path)
            remove_uv_lock(path)
            print()
        except Exception as e:
            raise
            # raise SystemExit(f"Processing Error for {path.name}:\n{e}\n") from e
    
    remove_uv_lock(Path.cwd())       

if __name__ == "__main__":
    main()
