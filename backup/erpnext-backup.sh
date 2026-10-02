#!/usr/bin/env bash
# Krypterad backup av ERPNext-siter till molnlagring via rclone.
#
# Bokföringslagen (7 kap.) kräver att räkenskapsinformationen bevaras i 7 år efter räkenskapsårets slut, i
# varaktigt skick. Den här scriptet laddar upp en gpg-krypterad backup (databas + filer) till varje rclone-mål
# i REMOTES, så att bokföringen finns kvar även om datorn går sönder.
#
#   erpnext-backup.sh            daglig backup (cron), månadskopia första körningen varje månad
#   erpnext-backup.sh arkiv ÅR   årsarkiv: SIE 4-fil per bolag + backup, raderas aldrig
#
# Struktur per mål och site:  <mål>/<site>/daglig/ÅÅÅÅ-MM-DD/   sparas DAILY_DAYS dagar
#                             <mål>/<site>/manad/ÅÅÅÅ-MM/       sparas MONTHLY_YEARS år
#                             <mål>/<site>/arkiv/ÅÅÅÅ/          raderas aldrig
#
# Inställningar läses från ~/.config/erpnext-backup/config (se config.example). Återställning: se README.

set -uo pipefail

CONFIG="${ERPNEXT_BACKUP_CONFIG:-$HOME/.config/erpnext-backup/config}"
if [ ! -r "$CONFIG" ]; then
	echo "$(date -Is) FEL: konfigurationen $CONFIG saknas" >&2
	exit 2
fi
# shellcheck source=/dev/null
source "$CONFIG"

: "${BENCH_DIR:?BENCH_DIR saknas i $CONFIG}"
: "${SITES:?SITES saknas i $CONFIG}"
: "${REMOTES:?REMOTES saknas i $CONFIG}"
: "${PASSPHRASE_FILE:?PASSPHRASE_FILE saknas i $CONFIG}"
DAILY_DAYS="${DAILY_DAYS:-30}"
MONTHLY_YEARS="${MONTHLY_YEARS:-8}"
BENCH="${BENCH:-$HOME/.local/bin/bench}"
RCLONE="${RCLONE:-$HOME/.local/bin/rclone}"
export PATH="$HOME/.local/bin:$PATH"

MODE="${1:-daglig}"
YEAR="${2:-}"
if [ "$MODE" = "arkiv" ] && ! [[ "$YEAR" =~ ^[0-9]{4}$ ]]; then
	echo "Användning: $0 arkiv ÅÅÅÅ" >&2
	exit 2
elif [ "$MODE" != "daglig" ] && [ "$MODE" != "arkiv" ]; then
	echo "Användning: $0 [daglig | arkiv ÅÅÅÅ]" >&2
	exit 2
fi

log() { echo "$(date -Is) $*"; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
STAMP="$(date +%Y-%m-%d_%H%M)"
FAILED=0

# Skapa backup (och vid arkiv SIE-filer) för en site och kryptera den till en fil. Skriver sökvägen på stdout,
# meddelanden på stderr.
make_archive() {
	local site="$1" dir="$TMP/$site"
	mkdir -p "$dir"
	if ! (cd "$BENCH_DIR" && "$BENCH" --site "$site" backup --with-files --backup-path "$dir/backup" >"$TMP/$site-bench.log" 2>&1); then
		log "FEL: bench backup misslyckades för $site (se nedan)" >&2
		tail -5 "$TMP/$site-bench.log" >&2
		return 1
	fi
	if [ "$MODE" = "arkiv" ]; then
		if ! (cd "$BENCH_DIR" && "$BENCH" --site "$site" execute erpnext_sverige.arkiv.skriv_sie_filer \
			--kwargs "{'katalog': '$dir/sie', 'ar': $YEAR}" >"$TMP/$site-sie.log" 2>&1); then
			log "FEL: SIE-export misslyckades för $site" >&2
			tail -5 "$TMP/$site-sie.log" >&2
			return 1
		fi
	fi
	local out="$TMP/$site-$MODE-$STAMP.tar.gpg"
	if ! tar -C "$dir" -cf - . | gpg --batch --yes --quiet --pinentry-mode loopback \
		--passphrase-file "$PASSPHRASE_FILE" --symmetric --cipher-algo AES256 -o "$out"; then
		log "FEL: kryptering misslyckades för $site" >&2
		return 1
	fi
	echo "$out"
}

for site in $SITES; do
	if ! archive="$(make_archive "$site")"; then
		FAILED=1
		continue
	fi
	name="$(basename "$archive")"
	for remote in $REMOTES; do
		base="${remote%/}/$site"
		if [ "$MODE" = "arkiv" ]; then
			targets=("arkiv/$YEAR")
		else
			targets=("daglig/$(date +%F)")
			month="manad/$(date +%Y-%m)"
			# Första lyckade körningen varje månad blir månadskopia (även om datorn var av den 1:a).
			if [ -z "$("$RCLONE" lsf "$base/$month" 2>/dev/null)" ]; then
				targets+=("$month")
			fi
		fi
		for target in "${targets[@]}"; do
			if "$RCLONE" copyto "$archive" "$base/$target/$name" 2>"$TMP/rclone.err"; then
				log "OK: $site → $base/$target/$name ($(du -h "$archive" | cut -f1))"
			else
				log "FEL: uppladdning till $base/$target misslyckades: $(tail -1 "$TMP/rclone.err")"
				FAILED=1
			fi
		done
		if [ "$MODE" = "daglig" ]; then
			"$RCLONE" delete "$base/daglig" --min-age "${DAILY_DAYS}d" --rmdirs 2>/dev/null || true
			"$RCLONE" delete "$base/manad" --min-age "$((MONTHLY_YEARS * 366))d" --rmdirs 2>/dev/null || true
		fi
	done
done

if [ "$FAILED" -ne 0 ]; then
	log "KLART MED FEL"
	exit 1
fi
log "KLART"
