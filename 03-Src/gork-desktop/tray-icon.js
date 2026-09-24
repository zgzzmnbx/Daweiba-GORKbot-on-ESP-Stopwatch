// Native tray pixels: do not pass SVG data URLs to Electron NativeImage.
// Neutral RGB values work with the native bitmap channel order on Windows.
function robotBitmap(size = 128) {
  const pixels = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = (x + .5) / size, v = (y + .5) / size;
      const radius = Math.hypot(u - .5, v - .5);
      if (radius > .47) continue;
      // A pale rim makes the black head readable on dark Windows taskbars.
      let shade = radius > .425 ? 225 : 20;
      for (const center of [.35, .65]) {
        const dx = u - center, dy = v - .48;
        const ex = dx * .966 + dy * .259;
        const ey = -dx * .259 + dy * .966;
        if (Math.hypot(ex, Math.max(0, Math.abs(ey) - .065)) < .065) shade = 255;
      }
      const i = (y * size + x) * 4;
      pixels[i] = pixels[i + 1] = pixels[i + 2] = shade;
      pixels[i + 3] = 255;
    }
  }
  return pixels;
}

function createTrayIcon(nativeImage) {
  const source = nativeImage.createFromBitmap(robotBitmap(), {width:128, height:128});
  if (source.isEmpty()) throw new Error('Gork tray bitmap could not be created');
  const icon = nativeImage.createEmpty();
  for (const scaleFactor of [1, 1.25, 1.5, 2, 3]) {
    const size = Math.round(16 * scaleFactor);
    const buffer = source.resize({width:size, height:size, quality:'best'}).toPNG();
    icon.addRepresentation({scaleFactor, buffer});
  }
  if (icon.isEmpty()) throw new Error('Gork tray icon has no image representations');
  return icon;
}
module.exports = {robotBitmap, createTrayIcon};
