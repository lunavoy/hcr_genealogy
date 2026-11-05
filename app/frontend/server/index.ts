import express, { type Request, type Response } from 'express'
import { existsSync } from 'node:fs'
import { join } from 'node:path'

const app = express()
const port = Number(process.env.PORT ?? 5100)
const pythonUrl = process.env.PYTHON_API_URL ?? 'http://127.0.0.1:5000'
const distRoot = join(import.meta.dirname, '..', '..', 'frontend', 'dist')

app.use(express.json({ limit: '10mb' }))

async function forward(req: Request, res: Response, targetPath: string) {
  const headers: Record<string, string> = {}
  const contentType = req.get('content-type')
  if (contentType) headers['content-type'] = contentType
  const body = req.method === 'GET' || req.method === 'HEAD'
    ? undefined
    : JSON.stringify(req.body ?? {})
  try {
    const response = await fetch(`${pythonUrl}${targetPath}`, {
      method: req.method,
      headers,
      body,
    })
    res.status(response.status)
    response.headers.forEach((value, key) => {
      if (key !== 'content-length' && key !== 'transfer-encoding') res.setHeader(key, value)
    })
    const buffer = Buffer.from(await response.arrayBuffer())
    res.send(buffer)
  } catch (error) {
    console.error('Falha ao encaminhar requisição para Python:', error)
    res.status(502).json({ error: 'Serviço Python indisponível.' })
  }
}

app.post('/recognize', (req, res) => void forward(req, res, '/api/recognize'))
app.post('/detect-layout', (req, res) => void forward(req, res, '/api/detect-layout'))
app.use('/api', (req, res) => void forward(req, res, req.originalUrl))

if (existsSync(distRoot)) {
  app.use(express.static(distRoot))
  app.get('/', (_req, res) => res.sendFile(join(distRoot, 'index.html')))
} else {
  app.get('/', (_req, res) => res.status(200).send('Frontend Vite ativo. Execute npm run dev para desenvolvimento.'))
}

app.listen(port, '127.0.0.1', () => {
  console.log(`Node API pública: http://127.0.0.1:${port}`)
  console.log(`Serviço Python interno: ${pythonUrl}`)
})
