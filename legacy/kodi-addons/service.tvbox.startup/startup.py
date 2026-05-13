import xbmc

monitor = xbmc.Monitor()

# Wait for Kodi/skin to finish loading.
if not monitor.waitForAbort(1):
    xbmc.executebuiltin("ActivateWindow(FavouritesBrowser)")
