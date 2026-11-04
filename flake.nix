{
  description = "CLIs for a student's own Canvas LMS work";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      ...
    }:
    (flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        packages.default = pkgs.callPackage ./nix/package.nix { };

        devShells.default =
          with pkgs;
          mkShell {
            buildInputs = [
              (python3.withPackages (
                ps: with ps; [
                  requests
                  pytest
                  responses
                ]
              ))
              ruff
            ];

            shellHook = ''
              # src layout: importable without installing.
              export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
            '';
          };
      }
    ))
    // {
      overlays.default = final: _prev: {
        canvas-cli = final.callPackage ./nix/package.nix { };
      };

      homeManagerModules.default = ./nix/hm-module.nix;
    };
}
