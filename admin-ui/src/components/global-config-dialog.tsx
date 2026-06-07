import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Settings } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { useGlobalConfig, useUpdateGlobalConfig } from '@/hooks/use-credentials'
import type { UpdateGlobalConfigRequest } from '@/types/api'
import { extractErrorMessage } from '@/lib/utils'

interface GlobalConfigDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function GlobalConfigDialog({ open, onOpenChange }: GlobalConfigDialogProps) {
  const { data: config, isLoading } = useGlobalConfig()
  const updateConfig = useUpdateGlobalConfig()

  const [region, setRegion] = useState('')
  const [authRegion, setAuthRegion] = useState('')
  const [apiRegion, setApiRegion] = useState('')
  const [defaultEndpoint, setDefaultEndpoint] = useState('ide')
  const [toolMode, setToolMode] = useState<'claude-code' | 'raw'>('claude-code')
  const [traceEnabled, setTraceEnabled] = useState(true)
  const [traceDays, setTraceDays] = useState('7')
  const [usageDays, setUsageDays] = useState('31')
  const [proxyUrl, setProxyUrl] = useState('')

  useEffect(() => {
    if (!open || !config) return
    setRegion(config.region || '')
    setAuthRegion(config.authRegion || '')
    setApiRegion(config.apiRegion || '')
    setDefaultEndpoint(config.defaultEndpoint || 'ide')
    setToolMode(config.toolCompatibilityMode || 'claude-code')
    setTraceEnabled(config.traceEnabled)
    setTraceDays(String(config.traceRetentionDays))
    setUsageDays(String(config.usageLogRetentionDays))
    setProxyUrl(config.proxyUrl || '')
  }, [open, config])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!config) return

    const nextTraceDays = Number.parseInt(traceDays, 10)
    const nextUsageDays = Number.parseInt(usageDays, 10)
    if (!region.trim()) {
      toast.error('Region 不能为空')
      return
    }
    if (!Number.isInteger(nextTraceDays) || nextTraceDays < 1 || nextTraceDays > 365) {
      toast.error('Trace 保留天数必须在 1 到 365 之间')
      return
    }
    if (!Number.isInteger(nextUsageDays) || nextUsageDays < 1 || nextUsageDays > 365) {
      toast.error('Usage 保留天数必须在 1 到 365 之间')
      return
    }

    const payload: UpdateGlobalConfigRequest = {}
    if (region.trim() !== config.region) payload.region = region.trim()
    if ((authRegion.trim() || null) !== (config.authRegion || null)) {
      payload.authRegion = authRegion.trim() || null
    }
    if ((apiRegion.trim() || null) !== (config.apiRegion || null)) {
      payload.apiRegion = apiRegion.trim() || null
    }
    if (defaultEndpoint !== config.defaultEndpoint) payload.defaultEndpoint = defaultEndpoint
    if (toolMode !== config.toolCompatibilityMode) payload.toolCompatibilityMode = toolMode
    if (traceEnabled !== config.traceEnabled) payload.traceEnabled = traceEnabled
    if (nextTraceDays !== config.traceRetentionDays) payload.traceRetentionDays = nextTraceDays
    if (nextUsageDays !== config.usageLogRetentionDays) payload.usageLogRetentionDays = nextUsageDays
    if ((proxyUrl.trim() || null) !== (config.proxyUrl || null)) {
      payload.proxyUrl = proxyUrl.trim() || null
    }

    if (Object.keys(payload).length === 0) {
      onOpenChange(false)
      return
    }

    updateConfig.mutate(payload, {
      onSuccess: () => {
        toast.success('全局配置已保存')
        onOpenChange(false)
      },
      onError: (err) => toast.error(`保存失败: ${extractErrorMessage(err)}`),
    })
  }

  const endpoints = config?.knownEndpoints?.length ? config.knownEndpoints : ['ide', 'cli']
  const pending = updateConfig.isPending

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent className="sm:max-w-xl max-h-[86vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            全局设置
          </DialogTitle>
          <DialogDescription>
            保存后立即更新运行时配置，并写回 config.json。
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="py-10 text-center text-sm text-muted-foreground">加载中...</div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-muted-foreground">Endpoint</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1.5">
                  <span className="text-sm font-medium">默认 Endpoint</span>
                  <select
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    value={defaultEndpoint}
                    onChange={(event) => setDefaultEndpoint(event.target.value)}
                    disabled={pending}
                  >
                    {endpoints.map((endpoint) => (
                      <option key={endpoint} value={endpoint}>
                        {endpoint}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1.5">
                  <span className="text-sm font-medium">工具兼容模式</span>
                  <select
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    value={toolMode}
                    onChange={(event) => setToolMode(event.target.value as 'claude-code' | 'raw')}
                    disabled={pending}
                  >
                    <option value="claude-code">claude-code</option>
                    <option value="raw">raw</option>
                  </select>
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="text-sm font-medium text-muted-foreground">Region</h3>
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="space-y-1.5">
                  <span className="text-sm font-medium">Region</span>
                  <Input value={region} onChange={(event) => setRegion(event.target.value)} disabled={pending} />
                </label>
                <label className="space-y-1.5">
                  <span className="text-sm font-medium">Auth Region</span>
                  <Input placeholder="默认跟随 Region" value={authRegion} onChange={(event) => setAuthRegion(event.target.value)} disabled={pending} />
                </label>
                <label className="space-y-1.5">
                  <span className="text-sm font-medium">API Region</span>
                  <Input placeholder="默认跟随 Region" value={apiRegion} onChange={(event) => setApiRegion(event.target.value)} disabled={pending} />
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="text-sm font-medium text-muted-foreground">代理</h3>
              <label className="space-y-1.5">
                <span className="text-sm font-medium">全局代理 URL</span>
                <Input
                  placeholder="http://127.0.0.1:7890 或 socks5://127.0.0.1:1080"
                  value={proxyUrl}
                  onChange={(event) => setProxyUrl(event.target.value)}
                  disabled={pending}
                />
              </label>
            </div>

            <div className="space-y-3">
              <h3 className="text-sm font-medium text-muted-foreground">日志保留</h3>
              <div className="flex items-center justify-between gap-4 rounded-md border border-border/70 px-3 py-2">
                <div>
                  <div className="text-sm font-medium">请求链路追踪</div>
                  <div className="text-xs text-muted-foreground">关闭后不再写入新的 traces.db 记录。</div>
                </div>
                <Switch checked={traceEnabled} onCheckedChange={setTraceEnabled} disabled={pending} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1.5">
                  <span className="text-sm font-medium">Trace 保留天数</span>
                  <Input type="number" min={1} max={365} value={traceDays} onChange={(event) => setTraceDays(event.target.value)} disabled={pending} />
                </label>
                <label className="space-y-1.5">
                  <span className="text-sm font-medium">Usage 保留天数</span>
                  <Input type="number" min={1} max={365} value={usageDays} onChange={(event) => setUsageDays(event.target.value)} disabled={pending} />
                </label>
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
                取消
              </Button>
              <Button type="submit" disabled={pending}>
                {pending ? '保存中...' : '保存'}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
