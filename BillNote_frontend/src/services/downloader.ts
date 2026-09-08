import request from '@/utils/request.ts'

export const getDownloaderCookie = async id => {
  return await request.get('/get_downloader_cookie/' + id)
}

export const updateDownloaderCookie = async (data: { cookie: string; platform: any }) => {
  return await request.post('/update_downloader_cookie', data)
}

export interface BiliQrcode {
  qrcode_key: string
  qr_png_base64: string
  login_url: string
}

export const getBiliQrcode = async (): Promise<BiliQrcode> => {
  return await request.get('/bili_qrcode')
}

export const getBiliQrcodeStatus = async (
  qrcode_key: string,
): Promise<{ status: 'pending' | 'scanned' | 'expired' | 'success'; cookie?: string }> => {
  return await request.get('/bili_qrcode/status', { params: { qrcode_key } })
}
