"""Typer CLI application for btrfs-churn-mon.

Entry point for all operations: monitor, report, analyse, status,
bootstrap, install, verify.

All commands (except install) call assert_not_root() to prevent
running as root — the service must run as unprivileged user.
"""

import time
from pathlib import Path
from typing import Optional

import typer

from src import assert_not_root
from src.aggregate import generate_aggregate
from src.btrfs import BtrfsClient
from src.config import Config, load_config
from src.install import CheckResult, CheckStatus, Installer
from src.log import setup_logging, get_logger
from src.monitor import find_pairs, read_state, write_state
from src.parser import aggregate as parse_aggregate, format_output
from src.report import generate_report

app = typer.Typer(
    name="btrfs-churn-mon",
    help="Analyze Btrfs snapshot churn — find what changes between snapshots.",
    invoke_without_command=True,
    no_args_is_help=True,
)


# --- State ---

_verbose = False


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Global options."""
    global _verbose
    _verbose = verbose
    setup_logging(verbose=verbose)


# --- Helper functions ---


def _get_config() -> Config:
    """Load config (respects CONFIG env var)."""
    return load_config()


def _run_install_check() -> None:
    """Run installation health-check and print results."""
    config = _get_config()
    installer = Installer(
        config=config,
        systemd_dir=Path("/etc/systemd/system"),
        sudoers_dir=Path("/etc/sudoers.d"),
        manage_systemd=False,
    )
    result = installer.check()

    if result.ok:
        typer.echo("✅ All checks passed.")
    else:
        typer.echo("❌ Installation issues found:")
        for issue in result.summary():
            typer.echo(f"  - {issue}")
        raise typer.Exit(code=1)


# --- Commands ---


@app.command()
def monitor(
    families: Optional[str] = typer.Option(None, "--families", envvar="SNAPSHOT_FAMILIES", help="Comma-separated snapshot families (default: all discovered)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show pairs without processing."),
) -> None:
    """Run monitoring cycle — find new pairs, dump, parse, report.

    Without --families (and no SNAPSHOT_FAMILIES env var), discovers and
    processes ALL families in snapdir.
    """
    assert_not_root()
    log = get_logger("monitor")
    config = _get_config()
    client = BtrfsClient(use_sudo=True)

    # Resolve families list
    if families:
        family_list = [f.strip() for f in families.split(",") if f.strip()]
    else:
        family_list = client.discover_families(config.snapdir)

    if not family_list:
        log.warning("No families found in snapdir %s", config.snapdir)
        typer.echo("No families found in snapdir.")
        return

    total_processed = 0

    for family in family_list:
        snapshots = client.find_snapshots(config.snapdir, family)
        log.debug("Family %s: %d snapshots found", family, len(snapshots))
        pairs = find_pairs(
            family=family,
            snapshots=snapshots,
            state_dir=config.state_dir,
            catchup_limit=config.catchup_limit,
        )

        if not pairs:
            log.info("[%s] Up-to-date — no pairs to process", family)
            typer.echo(f"[{family}] Up-to-date — no pairs to process.")
            continue

        if dry_run:
            typer.echo(f"[{family}] {len(pairs)} pair(s) to process:")
            for old, new in pairs:
                typer.echo(f"  {old.name} → {new.name}")
            continue

        for old, new in pairs:
            t_pair = time.time()
            log.info("[%s] Processing: %s → %s", family, old.name, new.name)
            typer.echo(f"[{family}] Processing: {old.name} → {new.name}")

            # Dump
            dump = client.send_dump(old, new)
            dump_lines = dump.count("\n")
            log.debug("[%s] Dump size: %d bytes, %d lines", family, len(dump), dump_lines)

            # Parse
            entries = parse_aggregate(dump.splitlines())
            n_entries = len(entries)
            total_churn = sum(entries.values()) if entries else 0
            detail_lines = format_output(entries)
            log.debug("[%s] Parsed %d unique paths, total churn %d bytes", family, n_entries, total_churn)

            # Save detail.tsv
            report_dir = config.reports_dir / family / new.name
            report_dir.mkdir(parents=True, exist_ok=True)
            detail_path = report_dir / "detail.tsv"
            detail_path.write_text(detail_lines, encoding="utf-8")

            # Generate report
            result = generate_report(detail_path)
            if result:
                md, json_data = result
                (report_dir / "report.md").write_text(md, encoding="utf-8")

            # Update state
            write_state(config.state_dir, family, new.name)
            elapsed = time.time() - t_pair
            log.info(
                "[%s] %s → %s | paths=%d, churn=%d bytes, time=%.1fs",
                family, old.name, new.name, n_entries, total_churn, elapsed,
            )

        total_processed += len(pairs)
        log.info("[%s] Done — %d pair(s) processed", family, len(pairs))
        typer.echo(f"[{family}] Done — {len(pairs)} pair(s) processed.")

    if not dry_run and total_processed == 0:
        typer.echo("All families up-to-date.")


@app.command()
def report(
    detail: Path = typer.Option(..., help="Path to detail.tsv file."),
    min_percent: float = typer.Option(5.0, help="Minimum percentage for smart expansion."),
    min_size: float = typer.Option(30.0, help="Minimum size (MiB) for smart expansion."),
) -> None:
    """Generate churn report from a detail.tsv file."""
    assert_not_root()

    result = generate_report(detail, min_percent=min_percent, min_size_mib=min_size)
    if result is None:
        typer.echo("No data — detail file is empty or missing.")
        return

    md, _ = result
    typer.echo(md)


@app.command()
def analyse(
    limit: Optional[str] = typer.Option(None, help="Time limit (e.g. '7d', '24h', '4w')."),
    top: int = typer.Option(50, help="Number of top entries."),
    family: Optional[str] = typer.Option(None, help="Filter by family."),
) -> None:
    """Generate aggregate churn report across all pairs."""
    assert_not_root()
    config = _get_config()

    reports_dir = config.reports_dir
    if family:
        reports_dir = reports_dir / family

    md, _ = generate_aggregate(reports_dir, limit=limit, top_n=top)
    typer.echo(md)


@app.command()
def status() -> None:
    """Show current configuration and state."""
    assert_not_root()
    config = _get_config()

    typer.echo("btrfs-churn-mon status")
    typer.echo(f"  prefix:    {config.prefix}")
    typer.echo(f"  snapdir:   {config.snapdir}")
    typer.echo(f"  reports:   {config.reports_dir}")
    typer.echo(f"  state:     {config.state_dir}")
    typer.echo(f"  catchup:   {config.catchup_limit}")

    # Show families with state
    if config.state_dir.is_dir():
        state_files = list(config.state_dir.glob("*.last"))
        if state_files:
            typer.echo("\n  Tracked families:")
            for sf in sorted(state_files):
                fam = sf.stem
                last = sf.read_text(encoding="utf-8").strip()
                typer.echo(f"    {fam}: {last}")
        else:
            typer.echo("\n  No tracked families (first run pending).")
    else:
        typer.echo("\n  State directory does not exist.")


@app.command()
def bootstrap(
    family: Optional[str] = typer.Option(None, help="Family to bootstrap (all if omitted)."),
    limit: int = typer.Option(100, help="Max pairs per family."),
) -> None:
    """Full historical bootstrap — process all available pairs."""
    assert_not_root()
    log = get_logger("bootstrap")
    config = _get_config()
    client = BtrfsClient(use_sudo=True)

    t_start = time.time()

    if family:
        families = [family]
    else:
        families = client.discover_families(config.snapdir)

    if not families:
        log.warning("No families found in %s", config.snapdir)
        typer.echo("No families found.")
        return

    log.info("Bootstrap started — families: %s, limit: %d/family", ", ".join(families), limit)
    total_pairs = 0
    total_bytes_dumped = 0
    total_entries = 0

    for fam in families:
        snapshots = client.find_snapshots(config.snapdir, fam)
        log.debug("[%s] %d snapshots found", fam, len(snapshots))

        if len(snapshots) < 2:
            log.info("[%s] Less than 2 snapshots — skipping", fam)
            typer.echo(f"[{fam}] Less than 2 snapshots — skipping.")
            continue

        pairs = [(snapshots[i], snapshots[i + 1]) for i in range(len(snapshots) - 1)]
        pairs = pairs[:limit]

        log.info("[%s] Bootstrapping %d pair(s)...", fam, len(pairs))
        typer.echo(f"[{fam}] Bootstrapping {len(pairs)} pair(s)...")

        for old, new in pairs:
            t_pair = time.time()
            dump = client.send_dump(old, new)
            dump_size = len(dump)
            dump_lines = dump.count("\n")
            total_bytes_dumped += dump_size

            entries = parse_aggregate(dump.splitlines())
            n_entries = len(entries)
            total_entries += n_entries
            total_churn = sum(entries.values()) if entries else 0
            detail_lines = format_output(entries)

            report_dir = config.reports_dir / fam / new.name
            report_dir.mkdir(parents=True, exist_ok=True)
            detail_path = report_dir / "detail.tsv"
            detail_path.write_text(detail_lines, encoding="utf-8")

            result = generate_report(detail_path)
            if result:
                md, _ = result
                (report_dir / "report.md").write_text(md, encoding="utf-8")

            write_state(config.state_dir, fam, new.name)
            elapsed = time.time() - t_pair

            log.info(
                "[%s] %s → %s | dump=%d lines, paths=%d, churn=%d bytes, time=%.1fs",
                fam, old.name, new.name, dump_lines, n_entries, total_churn, elapsed,
            )
            total_pairs += 1

        log.info("[%s] Bootstrap complete — %d pair(s)", fam, len(pairs))
        typer.echo(f"[{fam}] Bootstrap complete.")

    elapsed_total = time.time() - t_start
    log.info(
        "Bootstrap finished — %d pair(s), %d unique paths, %.1f MB dumped, %.1fs total",
        total_pairs, total_entries, total_bytes_dumped / 1048576, elapsed_total,
    )


@app.command()
def install(
    check: bool = typer.Option(False, "--check", help="Run health-check only (no modifications)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done."),
    force_env: bool = typer.Option(False, "--force-env", help="Overwrite /etc/default/btrfs-churn-mon if it differs."),
) -> None:
    """Install system components (user, sudoers, systemd, directories, env file).

    Requires sudo. Does NOT enforce root guard (installer needs privileges).
    """
    if check:
        _run_install_check()
        return

    # Install requires sudo — don't check root guard
    config = _get_config()
    installer = Installer(
        config=config,
        systemd_dir=Path("/etc/systemd/system"),
        sudoers_dir=Path("/etc/sudoers.d"),
    )

    if dry_run:
        typer.echo("Dry-run — would perform:")
        typer.echo("  1. Create user 'btrfs-churn' (system, no-home)")
        typer.echo("  2. Install /etc/sudoers.d/btrfs-churn-mon")
        typer.echo(f"  3. Create directories: {config.prefix}/{{reports,state}}")
        typer.echo("  4. Install systemd units + enable timer")
        typer.echo("  5. Install /etc/default/btrfs-churn-mon (environment file)")
        return

    typer.echo("Installing btrfs-churn-mon...")
    log = get_logger("install")
    log.info("Install started")
    installer.install_all()
    log.info("System components installed (user, sudoers, dirs, systemd)")

    # Environment file
    env_target = Path("/etc/default/btrfs-churn-mon")
    client = BtrfsClient(use_sudo=True)
    families = client.discover_families(config.snapdir)
    if not families:
        families = ["home"]  # sensible default

    env_result = installer.install_environment_file(
        env_target, families=families, force=force_env
    )
    if env_result == "created":
        log.info("Created %s (SNAPSHOT_FAMILIES=%s)", env_target, ",".join(families))
        typer.echo(f"  ✅ Created {env_target} (SNAPSHOT_FAMILIES={','.join(families)})")
    elif env_result == "unchanged":
        log.info("%s already up-to-date", env_target)
        typer.echo(f"  ℹ️  {env_target} already up-to-date")
    elif env_result == "updated":
        log.info("Updated %s (SNAPSHOT_FAMILIES=%s)", env_target, ",".join(families))
        typer.echo(f"  ✅ Updated {env_target} (SNAPSHOT_FAMILIES={','.join(families)})")
    elif env_result == "conflict":
        log.warning("%s exists with different content — kept as-is", env_target)
        typer.echo(f"  ⚠️  {env_target} exists with different content — kept as-is")
        typer.echo(f"      Use --force-env to overwrite, or edit manually.")

    log.info("Install complete")
    typer.echo("✅ Installation complete.")


@app.command()
def verify() -> None:
    """Verify installation (alias for install --check)."""
    _run_install_check()


@app.command()
def uninstall(
    purge_data: bool = typer.Option(False, "--purge-data", help="Remove reports and state directories."),
    keep_user: bool = typer.Option(False, "--keep-user", help="Do not delete the service user."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Uninstall system components (stops timer, removes units/sudoers/user).

    Config files are ALWAYS preserved. Data (reports/state) preserved unless --purge-data.
    """
    config = _get_config()

    if dry_run:
        typer.echo("Dry-run — would perform:")
        typer.echo("  1. Stop and disable btrfs-churn-mon.timer")
        typer.echo("  2. Remove systemd units (.service + .timer)")
        typer.echo("  3. Remove /etc/sudoers.d/btrfs-churn-mon")
        if purge_data:
            typer.echo(f"  4. Remove data: {config.prefix}/reports, {config.prefix}/state")
        else:
            typer.echo(f"  4. Preserve data: {config.prefix}/reports, {config.prefix}/state")
        if keep_user:
            typer.echo("  5. Preserve user 'btrfs-churn'")
        else:
            typer.echo("  5. Remove user 'btrfs-churn'")
        typer.echo("  ⚠️  Config files are NEVER removed.")
        return

    if not yes:
        typer.echo("Will uninstall btrfs-churn-mon:")
        typer.echo(f"  - Stop timer + remove systemd units")
        typer.echo(f"  - Remove sudoers")
        if purge_data:
            typer.echo(f"  - DELETE {config.prefix}/reports and {config.prefix}/state")
        if not keep_user:
            typer.echo(f"  - Remove user 'btrfs-churn'")
        typer.echo("  - Config files preserved.")
        confirm = typer.confirm("Proceed?")
        if not confirm:
            typer.echo("Aborted.")
            raise typer.Exit(code=0)

    installer = Installer(
        config=config,
        systemd_dir=Path("/etc/systemd/system"),
        sudoers_dir=Path("/etc/sudoers.d"),
    )

    log = get_logger("uninstall")
    log.info("Uninstall started (purge_data=%s, keep_user=%s)", purge_data, keep_user)
    typer.echo("Uninstalling btrfs-churn-mon...")
    installer.uninstall(purge_data=purge_data, keep_user=keep_user)
    log.info("Uninstall complete")
    typer.echo("✅ Uninstall complete.")
