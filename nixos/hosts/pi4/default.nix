{ lib, modulesPath, ... }:

{
  # The official generic AArch64 image includes Raspberry Pi 4 boot firmware.
  imports = [ "${modulesPath}/installer/sd-card/sd-image-aarch64.nix" ];

  nixpkgs.hostPlatform = "aarch64-linux";
  networking.hostName = "fpv-recorder";
  networking.useDHCP = lib.mkDefault true;
  hardware.enableRedistributableFirmware = true;
  boot.kernelModules = [ "uvcvideo" "snd-usb-audio" ];
  boot.zfs.forceImportRoot = false;
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  services.fpv-recorder.enable = true;
  services.openssh.enable = false;

  # Ethernet DHCP avoids waiting for Wi-Fi or network availability to record.
  system.stateVersion = "26.05";
}
