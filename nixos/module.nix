{ config, lib, pkgs, ... }:

let
  recorderConfig = config.services.fpv-recorder;
  recorderStateDirectoryName = "fpv-recorder";
  recorderStateDirectoryPath = "/var/lib/${recorderStateDirectoryName}";
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
    users.groups.fpv-recorder = { };
    users.users.fpv-recorder = {
      isSystemUser = true;
      group = "fpv-recorder";
      extraGroups = [ "video" "audio" ];
    };

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
        # Select the microphone directly without a desktop audio session.
        FPV_AUDIO_DEVICE_NAME = "plughw:CARD=CAMERA,DEV=0";
        FPV_RECORDINGS_DIRECTORY_PATH = "${recorderStateDirectoryPath}/recordings";
        PYTHONUNBUFFERED = "1";
      };
      serviceConfig = {
        Type = "simple";
        ExecStart = lib.getExe recorderConfig.package;
        User = "fpv-recorder";
        StateDirectory = recorderStateDirectoryName;
        StateDirectoryMode = "0750";
        WorkingDirectory = recorderStateDirectoryPath;
        Restart = "always";
        RestartSec = "2s";
        # Signal Python first; it asks FFmpeg to finalize before exiting.
        KillMode = "mixed";
        KillSignal = "SIGTERM";
        TimeoutStopSec = "20s";
        UMask = "0027";
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
      };
    };
  };
}
