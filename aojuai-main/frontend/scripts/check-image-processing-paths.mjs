/**
 * ALIGN-GAP G3: frontend lock of image_processing path prefixes
 * must stay a subset of the offline OpenAPI contract whitelist.
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const contractPath = join(
  here,
  '..',
  '..',
  'backend',
  'contracts',
  'realphotos_image_processing.openapi.json',
)
const locked = [
  '/api/v1/realphotos/assets',
  '/api/v1/realphotos/presets',
  '/api/v1/realphotos/processing-batches',
  '/api/v1/realphotos/processing-tasks',
  '/api/v1/realphotos/gateway/objects',
]

const contract = JSON.parse(readFileSync(contractPath, 'utf8'))
const prefixes = contract['x-image-processing-prefixes'] || []
for (const path of locked) {
  if (!prefixes.includes(path)) {
    console.error(`locked path missing from contract prefixes: ${path}`)
    process.exit(1)
  }
}
const forbidden = ['generation-tasks', 'prompt-optimizations', 'resource-imports', 'business-api-keys']
for (const route of Object.keys(contract.paths || {})) {
  if (forbidden.some((needle) => route.includes(needle))) {
    console.error(`contract leaked non-processing path: ${route}`)
    process.exit(1)
  }
}
console.log(`image_processing_paths_lock=ok locked=${locked.length}`)
