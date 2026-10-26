# Klipper, Moonraker and Mainsail

The local stack uses pinned images and the valid `PRINTER_DEVICE` substitution
instead of the old `${3D_PRINTER_DEVICE}` name, which begins with a digit.

Set `PRINTER_DEVICE` to the printer's actual host device, preferably a stable
`/dev/serial/by-id/...` path. Set `KLIPPER_CONFIG_DIR` to an existing absolute host
directory with these files:

- `klipper/printer.cfg`: your printer's actual firmware and hardware configuration.
- `moonraker/moonraker.conf`: Moonraker's API and access configuration.
- `mainsail/config.json`: Mainsail's configuration for the reachable Moonraker URL.

Prepare these files and their ownership before deployment. The stack deliberately
does not guess printer pins, motion limits, firmware or serial settings. Configure
the container-side printer device to match `PRINTER_DEVICE` in `printer.cfg`.
See the [Klipper configuration reference](https://www.klipper3d.org/Config_Reference.html)
and [Moonraker setup](https://moonraker.readthedocs.io/en/latest/installation/).

Mainsail defaults to host port 4070 and Moonraker to 7125. Keep the control API on
a trusted network and configure authentication/access control. The Docker daemon
must be allowed to map the selected device. Logs, the shared runtime socket and
G-code storage use named volumes; existing host configuration is not migrated.
