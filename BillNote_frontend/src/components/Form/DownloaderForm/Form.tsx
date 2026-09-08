// 下载器 Cookie 设置表单（最简化版）
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Form,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Loader2, QrCode } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import {
  getDownloaderCookie,
  updateDownloaderCookie,
  getBiliQrcode,
  getBiliQrcodeStatus,
} from '@/services/downloader' // 你自定义的请求
import { useParams } from 'react-router-dom'
import { videoPlatforms } from '@/constant/note.ts'

const CookieSchema = z.object({
  cookie: z.string().min(10, '请填写有效 Cookie'),
})

const DownloaderForm = () => {
  const form = useForm({
    resolver: zodResolver(CookieSchema),
    defaultValues: { cookie: '' },
  })
  const { id } = useParams()

  const [loading, setLoading] = useState(true)
  // B 站扫码登录
  const [qrOpen, setQrOpen] = useState(false)
  const [qrImg, setQrImg] = useState('')
  const [qrState, setQrState] = useState<'idle' | 'loading' | 'pending' | 'scanned' | 'expired'>('idle')
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }

  // 组件卸载 / 切换平台时停止轮询
  useEffect(() => stopPolling, [id])

  const startQrLogin = async () => {
    stopPolling()
    setQrState('loading')
    setQrOpen(true)
    try {
      const data = await getBiliQrcode()
      setQrImg(`data:image/png;base64,${data.qr_png_base64}`)
      setQrState('pending')
      pollTimerRef.current = setInterval(async () => {
        try {
          const res = await getBiliQrcodeStatus(data.qrcode_key)
          if (res.status === 'scanned') {
            setQrState('scanned')
          } else if (res.status === 'expired') {
            stopPolling()
            setQrState('expired')
          } else if (res.status === 'success') {
            stopPolling()
            setQrOpen(false)
            if (res.cookie) form.reset({ cookie: res.cookie })
            toast.success('扫码登录成功，Cookie 已自动保存')
          }
        } catch {
          // 单次轮询失败（网络抖动）不打断，下一轮继续
        }
      }, 2000)
    } catch {
      toast.error('获取二维码失败')
      setQrState('idle')
      setQrOpen(false)
    }
  }

  useEffect(() => {
    const loadCookie = async () => {
      setLoading(true) // 🔁 切换平台时显示 loading
      try {
        const res = await getDownloaderCookie(id)
        const cookie = res?.cookie || ''
        form.reset({ cookie }) // ✅ 正确重置表单值
      } catch (e) {
        toast.error('加载 Cookie 失败: ' + e)
        form.reset({ cookie: '' }) // ❗失败时也要清空旧值
      } finally {
        setLoading(false)
      }
    }

    if (id) loadCookie()
  }, [id]) // 🔁 每当 id 变化时触发

  const onSubmit = async values => {
    try {
      await updateDownloaderCookie({
        platform: id,
        cookie: String(values.cookie),
      })
      toast.success('保存成功')
    } catch {
      toast.error('保存失败')
    }
  }

  if (loading) return <div className="p-4">加载中...</div>

  return (
    <div className="max-w-xl p-4">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="text-lg font-bold">
            设置{videoPlatforms.find(item => item.value === id)?.label}下载器 Cookie
          </div>

          <FormField
            control={form.control}
            name="cookie"
            render={({ field }) => (
              <FormItem className="flex flex-col gap-2">
                <FormLabel>Cookie</FormLabel>
                <FormControl>
                  <Input {...field} placeholder="输入 Cookie" />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <div className="flex items-center gap-3">
            <Button type="submit">保存</Button>
            {id === 'bilibili' && (
              <Button type="button" variant="outline" onClick={startQrLogin}>
                <QrCode className="mr-1 h-4 w-4" />
                扫码登录（推荐）
              </Button>
            )}
          </div>
        </form>
      </Form>

      <Dialog open={qrOpen} onOpenChange={open => {
        setQrOpen(open)
        if (!open) stopPolling()
      }}>
        <DialogContent className="flex flex-col items-center">
          <DialogHeader>
            <DialogTitle>B 站扫码登录</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-neutral-500">使用手机 B 站 App 扫描二维码</p>
          <div className="flex h-56 w-56 items-center justify-center">
            {qrState === 'loading' ? (
              <Loader2 className="h-8 w-8 animate-spin text-neutral-400" />
            ) : qrState === 'expired' ? (
              <div className="flex flex-col items-center gap-3">
                <span className="text-sm text-neutral-500">二维码已过期</span>
                <Button size="sm" variant="outline" onClick={startQrLogin}>
                  刷新二维码
                </Button>
              </div>
            ) : (
              <img src={qrImg} alt="B 站登录二维码" className="h-56 w-56" />
            )}
          </div>
          {qrState === 'scanned' && (
            <p className="text-sm text-green-600">已扫码，请在手机上确认登录</p>
          )}
          {qrState === 'pending' && (
            <p className="text-sm text-neutral-400">等待扫码...</p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default DownloaderForm
