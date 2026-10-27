# bash completion for adopt
_adopt_completions() {
    local cur prev subcommands
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    subcommands="-S -U -B -Syu -Q -D -R --init --uninstall --version --help"

    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "$subcommands" -- "$cur") )
        return 0
    fi

    case "$prev" in
        -R|-U|-B)
            local apps=$(adopt -Q --json 2>/dev/null | grep '"id":' | cut -d'"' -f4)
            COMPREPLY=( $(compgen -W "$apps" -- "$cur") )
            return 0
            ;;
        -S)
            COMPREPLY=( $(compgen -f -X '!*.@(AppImage|appimage)' -- "$cur") )
            return 0
            ;;
    esac
}
complete -F _adopt_completions adopt
