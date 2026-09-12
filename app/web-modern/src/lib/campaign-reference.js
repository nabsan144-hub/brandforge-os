// Prepare privately in the browser. Upload occurs only with the campaign request.
export async function prepareCampaignReference(file) {
  if (!file || !['image/png', 'image/jpeg'].includes(file.type) || file.size > 10 * 1024 * 1024) throw new Error('Choose a PNG or JPEG smaller than 10 MB.')
  const bitmap = await createImageBitmap(file)
  try {
    if (bitmap.width * bitmap.height > 16000000) throw new Error('Choose a photograph below 16 million pixels.')
    const canvas = document.createElement('canvas')
    const scale = Math.min(1, 1440 / Math.max(bitmap.width, bitmap.height))
    canvas.width = Math.max(1, Math.round(bitmap.width * scale)); canvas.height = Math.max(1, Math.round(bitmap.height * scale))
    const ctx = canvas.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    for (const quality of [.85, .75, .65, .55, .45]) {
      const uri = canvas.toDataURL('image/jpeg', quality)
      if (uri.length <= 290000) return uri
    }
    throw new Error('This reference is too detailed for the upload limit. Use a smaller crop.')
  } finally { bitmap.close() }
}
