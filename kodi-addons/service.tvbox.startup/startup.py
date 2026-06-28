import xbmc

monitor = xbmc.Monitor()

# Wait for Kodi/skin to finish loading.
if not monitor.waitForAbort(.5):
    xbmc.executebuiltin("ActivateWindow(FavouritesBrowser)")
