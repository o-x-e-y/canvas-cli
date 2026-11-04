{
  lib,
  python3Packages,
}:

python3Packages.buildPythonApplication {
  pname = "canvas-cli";
  version = "0.1.0";
  pyproject = true;

  src = lib.cleanSource ../.;

  build-system = [ python3Packages.hatchling ];

  dependencies = [ python3Packages.requests ];

  nativeCheckInputs = with python3Packages; [
    pytestCheckHook
    responses
  ];

  pythonImportsCheck = [ "canvas_cli" ];

  meta = {
    description = "CLIs for a student's own Canvas LMS work";
    longDescription = ''
      canvas-assignment creates proof-of-work assignments with outcome rubrics
      in a personal course and hands files in, canvas-outcomes shows the
      standing on each learning outcome, and canvas-feedback reports new
      comments and assessments on submissions.
    '';
    license = lib.licenses.mit;
    platforms = lib.platforms.all;
  };
}
