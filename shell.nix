let 
  pkgs = import <nixpkgs> {};
in pkgs.mkShell {
  packages = with pkgs; [
    python311
    python311Packages.requests
    python311Packages.feedparser
  ];
}