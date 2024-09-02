The program is used for remotely turning on a computer and connecting via Remote Desktop.

The user defines a list of computers along with data such as:

* IP Address
* WOL Protocol Port
* RDP Protocol Port
* MAC Address of the computer’s network card
  
After pressing the button to turn on the computer, the program counts down 30 seconds, which is displayed on the status bar (in a graphical form). After this time, the user receives a notification that the computer is on and is asked whether they want to establish a Remote Desktop connection. If accepted, the program generates an .rdp file with the computer’s data, allowing the user to connect immediately. Once the session ends, the file is deleted to prevent the generation of junk files in the system.
