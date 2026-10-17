{ config, lib, pkgs, ... }:

let
  recorderConfig = config.services.fpv-recorder;
  recorderStateDirectoryName = "fpv-recorder";
  recorderStateDirectoryPath = "/var/lib/${recorderStateDirectoryName}";
  browserPort = 80;
in
{
  options.services.fpv-recorder = {
    enable = lib.mkEnableOption "automatic camera and microphone recording";
    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ./package.nix { };
      description = "Recorder package to run at boot.";
    };
  };

  config = lib.mkIf recorderConfig.enable {
    # The Pi's journal identifies the Ugreen lav adapter as C-Media 0d8c:0014.
    # Name its ALSA card independently of USB port and enumeration order.
    services.udev.extraRules = ''
      ACTION=="add", SUBSYSTEM=="sound", KERNEL=="card[0-9]*", ATTRS{idVendor}=="0d8c", ATTRS{idProduct}=="0014", ATTR{id}="LAV"
    '';

    users.groups.fpv-recorder = { };
    users.users.fpv-recorder = {
      isSystemUser = true;
      group = "fpv-recorder";
      extraGroups = [ "video" "audio" ];
    };

    networking.firewall.interfaces.wlan0.allowedTCPPorts = [ browserPort ];

    systemd.services.fpv-recorder = {
      description = "FPV camera and microphone recorder";
      wantedBy = [ "multi-user.target" ];
      after = [ "systemd-udev-trigger.service" "sound.target" ];
      wants = [ "sound.target" ];
      # Retry indefinitely when capture devices are missing or not ready yet.
      unitConfig = {
        StartLimitIntervalSec = 0;
        RequiresMountsFor = [ recorderStateDirectoryPath ];
      };
      environment = {
        # The udev rule names the separate Ugreen microphone adapter LAV.
        FPV_AUDIO_DEVICE_NAME = "plughw:CARD=LAV,DEV=0";
        FPV_RECORDINGS_DIRECTORY_PATH = "${recorderStateDirectoryPath}/recordings";
        FPV_WEB_BIND_ADDRESS = "0.0.0.0";
        FPV_WEB_PORT = toString browserPort;
        PYTHONUNBUFFERED = "1";
      };
      serviceConfig = {
        Type = "simple";
        ExecStart = lib.getExe recorderConfig.package;
        User = "fpv-recorder";
        StateDirectory = recorderStateDirectoryName;
        # Let another computer read recordings when the SD card is mounted.
        StateDirectoryMode = "0755";
        WorkingDirectory = recorderStateDirectoryPath;
        Restart = "always";
        RestartSec = "2s";
        # Signal Python first; it asks FFmpeg to finalize before exiting.
        KillMode = "mixed";
        KillSignal = "SIGTERM";
        TimeoutStopSec = "25s";
        UMask = "0022";
        NoNewPrivileges = true;
        AmbientCapabilities = [ "CAP_NET_BIND_SERVICE" ];
        CapabilityBoundingSet = [ "CAP_NET_BIND_SERVICE" ];
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
      };
    };
  };
}
