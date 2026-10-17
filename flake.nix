{
  description = "FPV recorder with automatic NixOS boot recording on Raspberry Pi 4";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs }: let
    supportedSystems = [ "aarch64-linux" "x86_64-linux" ];
    forEachSystem = nixpkgs.lib.genAttrs supportedSystems;
  in {
    packages = forEachSystem (system: let
      pkgs = import nixpkgs { inherit system; };
      recorderPackage = pkgs.callPackage ./nixos/package.nix { };
    in {
      default = recorderPackage;
      fpv-recorder = recorderPackage;
      sd-image = self.nixosConfigurations.fpv-recorder.config.system.build.sdImage;
    });

    nixosModules.default = import ./nixos/module.nix;

    nixosConfigurations.fpv-recorder = nixpkgs.lib.nixosSystem {
      modules = [
        self.nixosModules.default
        ./nixos/hosts/pi4
      ];
    };
  };
}
