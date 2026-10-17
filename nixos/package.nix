{ lib, stdenvNoCC, makeWrapper, python3, ffmpeg }:

let
  projectMetadata = (lib.importTOML ../pyproject.toml).project;
in
stdenvNoCC.mkDerivation {
  pname = "fpv-recorder";
  version = projectMetadata.version;

  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../main.py
      (lib.fileset.fileFilter (sourceFile: sourceFile.hasExt "py") ../recorder)
    ];
  };

  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/share/fpv-recorder" "$out/bin"
    cp main.py "$out/share/fpv-recorder/"
    cp -r recorder "$out/share/fpv-recorder/"
    makeWrapper ${python3}/bin/python3 "$out/bin/fpv-recorder" \
      --add-flags "$out/share/fpv-recorder/main.py" \
      --prefix PATH : ${lib.makeBinPath [ ffmpeg ]} \
      --run 'export FPV_RECORDINGS_DIRECTORY_PATH="''${FPV_RECORDINGS_DIRECTORY_PATH:-$PWD/recordings}"' \
      --set PYTHONDONTWRITEBYTECODE 1
    runHook postInstall
  '';

  meta = {
    description = "Record USB camera video and microphone audio using FFmpeg";
    platforms = lib.platforms.linux;
    mainProgram = "fpv-recorder";
  };
}
