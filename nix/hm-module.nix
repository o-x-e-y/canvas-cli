{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.programs.canvas;
in
{
  options.programs.canvas = {
    enable = lib.mkEnableOption "the Canvas CLIs";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.canvas-cli;
      defaultText = lib.literalExpression "pkgs.canvas-cli";
      description = ''
        The package to install. The default needs this flake's
        `overlays.default` in `nixpkgs.overlays`.
      '';
    };

    url = lib.mkOption {
      type = lib.types.str;
      example = "https://school.instructure.com";
      description = "The Canvas instance.";
    };

    apiKeyFile = lib.mkOption {
      type = lib.types.str;
      example = "/run/secrets/canvas-api-key";
      description = ''
        A file holding a Canvas access token (Account, Settings, New access
        token). A path as a string, so the token stays out of the Nix store.
      '';
    };

    editor = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "codium --wait";
      description = ''
        The editor `canvas assignment` opens for its form when no `--name` is
        given. It must wait until the file is closed. Null falls back to
        `$EDITOR`.
      '';
    };

    feedback = {
      enable = lib.mkEnableOption "a desktop notification for new feedback on your submissions";

      interval = lib.mkOption {
        type = lib.types.str;
        default = "hourly";
        description = "How often to check, as a systemd OnCalendar expression.";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ cfg.package ];

    xdg.configFile."canvas/settings.json".text = builtins.toJSON (
      {
        inherit (cfg) url;
        api_key_file = cfg.apiKeyFile;
      }
      // lib.optionalAttrs (cfg.editor != null) { inherit (cfg) editor; }
    );

    systemd.user.services.canvas-feedback = lib.mkIf cfg.feedback.enable {
      Unit.Description = "Notify about new feedback on Canvas submissions";
      Service = {
        Type = "oneshot";
        Environment = "PATH=${pkgs.libnotify}/bin";
        ExecStart = "${lib.getExe cfg.package} feedback --notify";
      };
    };

    systemd.user.timers.canvas-feedback = lib.mkIf cfg.feedback.enable {
      Unit.Description = "Check Canvas for new feedback";
      Timer = {
        OnCalendar = cfg.feedback.interval;
        Persistent = true;
      };
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
