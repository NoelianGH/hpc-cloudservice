# Sambutan saat relawan login ke compute node (isi dari agen: ~/.hpc-motd)
case "$-" in
  *i*) [ -f "$HOME/.hpc-motd" ] && cat "$HOME/.hpc-motd" ;;
esac
