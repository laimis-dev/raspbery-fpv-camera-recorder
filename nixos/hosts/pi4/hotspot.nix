{ ... }:

let
  hotspotInterfaceName = "wlan0";
  hotspotAddress = "192.168.4.1";
in
{
  # The built-in radio is dedicated to the offline recorder hotspot.
  networking.usePredictableInterfaceNames = false;
  networking.wireless.enable = false;
  networking.networkmanager.enable = false;
  networking.interfaces.${hotspotInterfaceName} = {
    useDHCP = false;
    ipv4.addresses = [ { address = hotspotAddress; prefixLength = 24; } ];
  };

  services.hostapd = {
    enable = true;
    radios.${hotspotInterfaceName} = {
      band = "2g";
      channel = 6;
      countryCode = "LT";
      wifi4.capabilities = [ ];
      wifi5.enable = false;
      networks.${hotspotInterfaceName} = {
        ssid = "FPV-Recorder";
        authentication = {
          mode = "wpa2-sha1";
          wpaPassword = "12345678";
        };
      };
    };
  };

  services.dnsmasq = {
    enable = true;
    settings = {
      interface = hotspotInterfaceName;
      listen-address = hotspotAddress;
      bind-dynamic = true;
      domain-needed = true;
      bogus-priv = true;
      no-resolv = true;
      dhcp-authoritative = true;
      dhcp-range = [ "192.168.4.10,192.168.4.200,255.255.255.0,12h" ];
      # No default route: this access point does not provide internet access.
      dhcp-option = [ "3" "6,${hotspotAddress}" ];
      address = [ "/recorder.lan/${hotspotAddress}" ];
    };
  };

  networking.firewall.interfaces.${hotspotInterfaceName} = {
    allowedUDPPorts = [ 53 67 ];
    allowedTCPPorts = [ 53 ];
  };
}
