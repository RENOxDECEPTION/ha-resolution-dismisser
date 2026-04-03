#!/usr/bin/with-contenv bash
# shellcheck shell=bash
# ==============================================================================
# Home Assistant Add-on: Resolution Dismisser
# Automatically dismisses configurable resolution center warnings
# ==============================================================================
set -e

# ------------------------------------------------------------------------------
# Graceful shutdown on SIGTERM/SIGINT
# ------------------------------------------------------------------------------
RUNNING=true
trap 'RUNNING=false' SIGTERM SIGINT

# ------------------------------------------------------------------------------
# Read add-on options
# ------------------------------------------------------------------------------
CONFIG_PATH="/data/options.json"
ADDON_CONFIG="/addon/config.yaml"  # mounted by HA add-on framework
SUPERVISOR_API="http://supervisor"

CHECK_INTERVAL=$(jq -r '.check_interval' "$CONFIG_PATH")
LOG_LEVEL=$(jq -r '.log_level // "info"' "$CONFIG_PATH")

# Build arrays from boolean toggles + custom entries
DISMISS_ISSUES=()
DISMISS_SUGGESTIONS=()
DISMISS_REPAIRS=()

# Issues - check each boolean toggle
for key in no_current_backup dns_server_failed free_space multiple_data_disks security trust update_failed fatal_error reboot_required; do
    val=$(jq -r ".issue_${key} // false" "$CONFIG_PATH")
    [[ "$val" == "true" ]] && DISMISS_ISSUES+=("$key")
done

# Suggestions - check each boolean toggle
for key in create_full_backup clear_full_backup execute_repair execute_update execute_reload execute_remove execute_reset execute_stop; do
    val=$(jq -r ".suggestion_${key} // false" "$CONFIG_PATH")
    [[ "$val" == "true" ]] && DISMISS_SUGGESTIONS+=("$key")
done

# Repairs - check each boolean toggle
for key in unsupported_system_os unsupported_system_software unsupported_system_job_conditions unsupported_system_connectivity_check unsupported_system_content_trust unsupported_system_dns_server unsupported_system_docker_configuration unsupported_system_network_manager unsupported_system_os_agent unsupported_system_privileged unsupported_system_systemd unsupported_system_cgroup_version unhealthy_system_docker unhealthy_system_supervisor unhealthy_system_setup unhealthy_system_privileged unhealthy_system_untrusted deprecated_method; do
    val=$(jq -r ".repair_${key} // false" "$CONFIG_PATH")
    [[ "$val" == "true" ]] && DISMISS_REPAIRS+=("$key")
done

# Add custom entries
while IFS= read -r item; do
    [[ -n "$item" ]] && DISMISS_ISSUES+=("$item")
done < <(jq -r '.custom_dismiss_issues[]? // empty' "$CONFIG_PATH")

while IFS= read -r item; do
    [[ -n "$item" ]] && DISMISS_SUGGESTIONS+=("$item")
done < <(jq -r '.custom_dismiss_suggestions[]? // empty' "$CONFIG_PATH")

while IFS= read -r item; do
    [[ -n "$item" ]] && DISMISS_REPAIRS+=("$item")
done < <(jq -r '.custom_dismiss_repairs[]? // empty' "$CONFIG_PATH")

# ------------------------------------------------------------------------------
# Logging helpers
# ------------------------------------------------------------------------------
log_debug()  { [[ "$LOG_LEVEL" == "debug" ]] && echo "[DEBUG] $*" >&2 || true; }
log_info()   { [[ "$LOG_LEVEL" =~ ^(debug|info)$ ]] && echo "[INFO]  $*" >&2 || true; }
log_warn()   { [[ "$LOG_LEVEL" =~ ^(debug|info|warning)$ ]] && echo "[WARN]  $*" >&2 || true; }
log_error()  { echo "[ERROR] $*" >&2; }

# Interruptible sleep — exits early on SIGTERM/SIGINT
interruptible_sleep() {
    local secs=$1 i=0
    while (( i < secs )) && [[ "$RUNNING" == "true" ]]; do
        sleep 1
        (( i++ )) || true
    done
}

# ------------------------------------------------------------------------------
# API helper — calls the Supervisor REST API
# ------------------------------------------------------------------------------
api_call() {
    local method="$1"
    local endpoint="$2"
    local response
    local http_code

    response=$(curl -s -w "\n%{http_code}" \
        -X "$method" \
        -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
        -H "Content-Type: application/json" \
        "${SUPERVISOR_API}${endpoint}" 2>/dev/null) || true

    http_code=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | head -n -1)

    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
        echo "$body"
        return 0
    else
        log_debug "API call $method $endpoint returned HTTP $http_code"
        return 1
    fi
}

# ------------------------------------------------------------------------------
# Fetches current resolution info from the Supervisor
# ------------------------------------------------------------------------------
fetch_resolution_info() {
    api_call GET "/resolution/info"
}

# ------------------------------------------------------------------------------
# Dismiss matching issues
# ------------------------------------------------------------------------------
dismiss_matching_issues() {
    local info="$1"

    if [[ ${#DISMISS_ISSUES[@]} -eq 0 ]]; then
        log_debug "No issue types configured for dismissal"
        return
    fi

    local issue_count
    issue_count=$(echo "$info" | jq '.data.issues | length')
    log_debug "Found $issue_count active issue(s)"

    for issue_type in "${DISMISS_ISSUES[@]}"; do
        # Find all issues matching this type
        local matching_uuids
        mapfile -t matching_uuids < <(echo "$info" | jq -r \
            --arg type "$issue_type" \
            '.data.issues[] | select(.type == $type) | .uuid')

        for uuid in "${matching_uuids[@]}"; do
            [[ -z "$uuid" ]] && continue
            log_info "Dismissing issue: type=$issue_type uuid=$uuid"
            if api_call DELETE "/resolution/issue/$uuid" > /dev/null; then
                log_info "  -> Dismissed successfully"
            else
                log_warn "  -> Failed to dismiss issue $uuid"
            fi
        done
    done
}

# ------------------------------------------------------------------------------
# Dismiss matching suggestions
# ------------------------------------------------------------------------------
dismiss_matching_suggestions() {
    local info="$1"

    if [[ ${#DISMISS_SUGGESTIONS[@]} -eq 0 ]]; then
        log_debug "No suggestion types configured for dismissal"
        return
    fi

    local suggestion_count
    suggestion_count=$(echo "$info" | jq '.data.suggestions | length')
    log_debug "Found $suggestion_count active suggestion(s)"

    for suggestion_type in "${DISMISS_SUGGESTIONS[@]}"; do
        local matching_uuids
        mapfile -t matching_uuids < <(echo "$info" | jq -r \
            --arg type "$suggestion_type" \
            '.data.suggestions[] | select(.type == $type) | .uuid')

        for uuid in "${matching_uuids[@]}"; do
            [[ -z "$uuid" ]] && continue
            log_info "Dismissing suggestion: type=$suggestion_type uuid=$uuid"
            if api_call DELETE "/resolution/suggestion/$uuid" > /dev/null; then
                log_info "  -> Dismissed successfully"
            else
                log_warn "  -> Failed to dismiss suggestion $uuid"
            fi
        done
    done
}

# ------------------------------------------------------------------------------
# Dismiss matching HA Core repairs (via WebSocket API)
# ------------------------------------------------------------------------------
dismiss_matching_repairs() {
    if [[ ${#DISMISS_REPAIRS[@]} -eq 0 ]]; then
        log_debug "No repair types configured for dismissal"
        return
    fi

    local result
    result=$(python3 /dismiss_repairs.py "${DISMISS_REPAIRS[@]}" 2>&1) || {
        log_warn "Failed to run repair dismissal script: $result"
        return
    }

    local listed
    listed=$(echo "$result" | jq -r '.listed // 0')
    log_debug "Found $listed HA Core repair(s)"

    # Log all discovered repairs at debug level
    local all_repairs
    all_repairs=$(echo "$result" | jq -r '.all_repairs[]? | "\(.domain).\(.issue_id) (dismissed=\(.dismissed))"')
    if [[ -n "$all_repairs" ]]; then
        while IFS= read -r line; do
            log_debug "  Repair: $line"
        done <<< "$all_repairs"
    fi

    # Log dismissal results
    local dismissed_count
    dismissed_count=$(echo "$result" | jq '.dismissed | length')
    if [[ "$dismissed_count" -gt 0 ]]; then
        log_info "Dismissed $dismissed_count repair(s)"

        local dismissed
        dismissed=$(echo "$result" | jq -r '.dismissed[]? | "type=\(.domain).\(.issue_id) success=\(.success)"')
        if [[ -n "$dismissed" ]]; then
            while IFS= read -r line; do
                log_info "  $line"
            done <<< "$dismissed"
        fi
    fi

    # Log full raw result at debug
    log_debug "Raw dismiss_repairs.py output: $result"

    # Log errors
    local errors
    errors=$(echo "$result" | jq -r '.errors[]? // empty')
    if [[ -n "$errors" ]]; then
        while IFS= read -r line; do
            log_warn "Repair dismissal: $line"
        done <<< "$errors"
    fi
}

# ------------------------------------------------------------------------------
# Log current unsupported/unhealthy status (informational)
# ------------------------------------------------------------------------------
log_system_status() {
    local info="$1"

    local unsupported
    unsupported=$(echo "$info" | jq -r '.data.unsupported | join(", ")')
    local unhealthy
    unhealthy=$(echo "$info" | jq -r '.data.unhealthy | join(", ")')

    if [[ -n "$unsupported" && "$unsupported" != "" ]]; then
        log_debug "Unsupported reasons: $unsupported"
    fi
    if [[ -n "$unhealthy" && "$unhealthy" != "" ]]; then
        log_debug "Unhealthy reasons: $unhealthy"
    fi
}

# ==============================================================================
# Main loop
# ==============================================================================
main() {
    local version
    version=$(grep '^version:' "$ADDON_CONFIG" 2>/dev/null | sed 's/version: *"\?\([^"]*\)"\?/\1/' || echo "unknown")

    log_info "========================================="
    log_info " Resolution Dismisser v${version}"
    log_info "========================================="
    log_info "Check interval: ${CHECK_INTERVAL}s"
    log_info "Log level: ${LOG_LEVEL}"

    if [[ ${#DISMISS_ISSUES[@]} -gt 0 ]]; then
        log_info "Issue types to dismiss: ${DISMISS_ISSUES[*]}"
    else
        log_info "No issue types configured for dismissal"
    fi

    if [[ ${#DISMISS_SUGGESTIONS[@]} -gt 0 ]]; then
        log_info "Suggestion types to dismiss: ${DISMISS_SUGGESTIONS[*]}"
    else
        log_info "No suggestion types configured for dismissal"
    fi

    if [[ ${#DISMISS_REPAIRS[@]} -gt 0 ]]; then
        log_info "Repair types to dismiss: ${DISMISS_REPAIRS[*]}"
    else
        log_info "No repair types configured for dismissal"
    fi

    log_info "-----------------------------------------"

    # Wait for supervisor to become ready (retry with backoff)
    local backoff=5
    while [[ "$RUNNING" == "true" ]]; do
        local probe
        probe=$(fetch_resolution_info 2>/dev/null) && \
            echo "$probe" | jq -e '.data' > /dev/null 2>&1 && break
        log_info "Supervisor not ready yet, retrying in ${backoff}s..."
        interruptible_sleep "$backoff"
        (( backoff = backoff < 30 ? backoff * 2 : 30 )) || true
    done

    while [[ "$RUNNING" == "true" ]]; do
        log_debug "Checking resolution center..."

        local resolution_info
        resolution_info=$(fetch_resolution_info) || {
            log_warn "Failed to fetch resolution info, retrying in ${CHECK_INTERVAL}s"
            interruptible_sleep "$CHECK_INTERVAL"
            continue
        }

        # Verify we got valid JSON
        if ! echo "$resolution_info" | jq -e '.data' > /dev/null 2>&1; then
            log_warn "Invalid response from resolution API, retrying in ${CHECK_INTERVAL}s"
            interruptible_sleep "$CHECK_INTERVAL"
            continue
        fi

        log_system_status "$resolution_info"
        dismiss_matching_issues "$resolution_info"
        dismiss_matching_suggestions "$resolution_info"
        dismiss_matching_repairs

        log_debug "Check complete. Sleeping ${CHECK_INTERVAL}s..."
        interruptible_sleep "$CHECK_INTERVAL"
    done

    log_info "Received shutdown signal, exiting gracefully."
}

main
