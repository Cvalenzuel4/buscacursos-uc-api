# 🎓 BuscaCursos UC API

API RESTful para obtener información de cursos desde el catálogo de [BuscaCursos UC](https://buscacursos.uc.cl/).

## ✨ Características

- 🔍 **Búsqueda de cursos** por sigla, semestre, profesor y campus
- 📅 **Horarios estructurados** con tipo, día, módulos y sala
- ⚡ **Caché inteligente** (5 minutos) para evitar peticiones repetidas
- 🛡️ **Bypass de Cloudflare** con curl_cffi + Chrome impersonation
- 🔄 **CORS habilitado** para uso desde cualquier frontend

## 🚀 Endpoints

### Buscar Cursos
```http
GET /api/v1/cursos/buscar?sigla=ICS2123&semestre=2026-1
```

**Parámetros:**
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `sigla` | string | ✅ | Código del curso (ej: ICS2123, MAT1610) |
| `semestre` | string | ✅ | Semestre en formato YYYY-S (ej: 2026-1) |
| `profesor` | string | ❌ | Filtrar por nombre del profesor |
| `campus` | string | ❌ | Filtrar por campus |

**Respuesta:**
```json
{
  "success": true,
  "data": [
    {
      "nrc": "16515",
      "sigla": "ICS2123",
      "seccion": 1,
      "nombre": "Modelos Estocásticos",
      "profesor": "Verdugo Victor",
      "campus": "San Joaquín",
      "creditos": 10,
      "vacantes_totales": 140,
      "vacantes_disponibles": 140,
      "horarios": [
        {
          "tipo": "CLAS",
          "dia": "Lunes",
          "modulos": [2],
          "sala": null
        },
        {
          "tipo": "CLAS",
          "dia": "Miércoles",
          "modulos": [2],
          "sala": null
        },
        {
          "tipo": "AYU",
          "dia": "Viernes",
          "modulos": [2],
          "sala": null
        }
      ],
      "requiere_laboratorio": false
    }
  ],
  "message": "Se encontraron 4 secciones",
  "meta": {
    "sigla": "ICS2123",
    "semestre": "2026-1",
    "total_secciones": 4
  }
}
```

### Info de Curso (alias)
```http
GET /api/v1/cursos/info/{sigla}?semestre=2026-1
```

### Buscar Múltiples Cursos (Paralelo)
```http
POST /api/v1/cursos/buscar-multiple
Content-Type: application/json

{
  "siglas": ["ICS2123", "MAT1610", "FIS1513"],
  "semestre": "2026-1"
}
```

**Ventajas:**
- ⚡ Una sola petición HTTP para múltiples siglas
- 🚀 Ejecución paralela: 5 siglas toman casi el mismo tiempo que 1
- ✅ Resultados individuales por sigla (éxito/error separados)

**Límites:**
- Máximo 20 siglas por petición

**Respuesta:**
```json
{
  "success": true,
  "data": [
    {
      "sigla": "ICS2123",
      "success": true,
      "cursos": [
        {
          "nrc": "16515",
          "sigla": "ICS2123",
          "seccion": 1,
          "nombre": "Modelos Estocásticos",
          "profesor": "Verdugo Victor",
          "horarios": [...]
        }
      ],
      "error": null
    },
    {
      "sigla": "MAT1610",
      "success": true,
      "cursos": [...],
      "error": null
    },
    {
      "sigla": "INVALID",
      "success": false,
      "cursos": [],
      "error": "No se encontraron cursos"
    }
  ],
  "message": "Búsqueda completada: 2/3 siglas exitosas, 8 secciones encontradas",
  "meta": {
    "semestre": "2026-1",
    "siglas_solicitadas": 3,
    "siglas_exitosas": 2,
    "total_secciones": 8
  }
}
```

### Health Check
```http
GET /api/v1/health
```

## 📋 Mapeo de Días

| Código | Día |
|--------|-----|
| L | Lunes |
| M | Martes |
| W | **Miércoles** |
| J | Jueves |
| V | Viernes |
| S | Sábado |

> ⚠️ **Nota:** BuscaCursos UC usa `W` para Miércoles (Wednesday), no `X`.

## 🛠️ Desarrollo Local

### Requisitos
- Python 3.11+
- pip

### Instalación
```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/buscacursos-uc-api.git
cd buscacursos-uc-api

# Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Copiar variables de entorno
cp .env.example .env

# Ejecutar servidor
python -m app.main
```

El servidor estará disponible en `http://localhost:8000`

### Documentación Interactiva
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🐳 Docker

```bash
# Construir imagen
docker build -t buscacursos-api .

# Ejecutar contenedor
docker run -p 8000:8000 buscacursos-api
```

## ☁️ Deploy

### Railway
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)

1. Conecta tu repositorio de GitHub
2. Railway detectará automáticamente el Dockerfile
3. La API estará disponible en tu URL de Railway

### Render
1. Crea un nuevo Web Service
2. Conecta tu repositorio
3. Render detectará el Dockerfile automáticamente

### Variables de Entorno (Producción)
```env
ENVIRONMENT=production
ALLOWED_ORIGINS=https://tu-frontend.com,https://otro-frontend.com
CACHE_TTL_SECONDS=300
LOG_LEVEL=INFO
```

## 📊 Rate Limiting

La API implementa caché de 5 minutos para evitar sobrecargar BuscaCursos UC.
Si necesitas datos más frescos, espera a que expire el caché.

## 🤝 Uso desde Frontend

### JavaScript/TypeScript
```javascript
const API_URL = 'https://tu-api.railway.app';

async function buscarCursos(sigla, semestre = '2026-1') {
  const response = await fetch(
    `${API_URL}/api/v1/cursos/buscar?sigla=${sigla}&semestre=${semestre}`
  );
  const data = await response.json();
  
  if (data.success) {
    return data.data;
  }
  throw new Error(data.message);
}

// Búsqueda múltiple (paralela)
async function buscarMultiplesCursos(siglas, semestre = '2026-1') {
  const response = await fetch(`${API_URL}/api/v1/cursos/buscar-multiple`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ siglas, semestre })
  });
  const data = await response.json();
  
  if (data.success) {
    // data.data es un array con resultados por sigla
    return data.data;
  }
  throw new Error(data.message);
}

// Uso individual
const cursos = await buscarCursos('ICS2123');

// Uso múltiple - una sola petición para todas las siglas
const resultados = await buscarMultiplesCursos(['ICS2123', 'MAT1610', 'FIS1513']);
resultados.forEach(r => {
  if (r.success) {
    console.log(`${r.sigla}: ${r.cursos.length} secciones`);
  } else {
    console.log(`${r.sigla}: Error - ${r.error}`);
  }
});
```

### Python
```python
import requests

API_URL = 'https://tu-api.railway.app'

def buscar_cursos(sigla: str, semestre: str = '2026-1'):
    response = requests.get(
        f'{API_URL}/api/v1/cursos/buscar',
        params={'sigla': sigla, 'semestre': semestre}
    )
    data = response.json()
    
    if data['success']:
        return data['data']
    raise Exception(data['message'])

# Búsqueda múltiple (paralela)
def buscar_multiples_cursos(siglas: list[str], semestre: str = '2026-1'):
    response = requests.post(
        f'{API_URL}/api/v1/cursos/buscar-multiple',
        json={'siglas': siglas, 'semestre': semestre}
    )
    data = response.json()
    
    if data['success']:
        return data['data']
    raise Exception(data['message'])

# Uso individual
cursos = buscar_cursos('ICS2123')

# Uso múltiple
resultados = buscar_multiples_cursos(['ICS2123', 'MAT1610', 'FIS1513'])
for r in resultados:
    if r['success']:
        print(f"{r['sigla']}: {len(r['cursos'])} secciones")
    else:
        print(f"{r['sigla']}: Error - {r['error']}")
```

## 📄 Licencia

MIT License - Proyecto open-source para la comunidad UC.

## 👤 Autor

Desarrollado para facilitar la organización de horarios universitarios.
