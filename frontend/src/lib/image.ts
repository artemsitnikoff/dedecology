// Клиентское сжатие фото перед загрузкой в публичной форме.
//
// Зачем: телефонные фото бывают по 8–12 МБ, и три штуки упираются в лимит тела
// запроса (nginx/внешний прокси → HTTP 413), а ещё долго грузятся. Уменьшаем по
// большой стороне до maxDim и перекодируем в JPEG — тело становится ~1–2 МБ/фото
// и форма работает за любым прокси. Сервер ВСЁ РАВНО делает финальный ресайз
// (1600/400) — это лишь дешёвая предобработка на клиенте, не замена серверной.
//
// Любой сбой (не картинка, неподдерживаемый формат вроде HEIC, ошибка canvas) →
// возвращаем исходный файл без изменений, чтобы НЕ ломать отправку.

const MAX_DIM = 2048; // потолок большей стороны, px
const QUALITY = 0.85; // качество JPEG (баланс размер/детализация)

export async function compressImage(
  file: File,
  maxDim: number = MAX_DIM,
  quality: number = QUALITY,
): Promise<File> {
  if (!file.type.startsWith('image/')) return file;

  let bitmap: ImageBitmap | null = null;
  try {
    // imageOrientation: 'from-image' — учесть EXIF-поворот (фото с телефона
    // часто повёрнуты флагом ориентации, без этого они «лягут на бок»).
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
    const { width, height } = bitmap;
    if (!width || !height) return file;

    const scale = Math.min(1, maxDim / Math.max(width, height));
    const w = Math.max(1, Math.round(width * scale));
    const h = Math.max(1, Math.round(height * scale));

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) return file;
    ctx.drawImage(bitmap, 0, 0, w, h);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', quality),
    );
    if (!blob) return file;

    // Если перекодировка не дала выигрыша (исходник уже маленький JPEG) — оставляем оригинал.
    if (file.type === 'image/jpeg' && blob.size >= file.size) return file;

    const name = file.name.replace(/\.[^.]+$/, '') + '.jpg';
    return new File([blob], name, { type: 'image/jpeg', lastModified: Date.now() });
  } catch {
    return file;
  } finally {
    bitmap?.close();
  }
}
