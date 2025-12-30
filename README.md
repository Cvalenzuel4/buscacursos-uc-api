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

// Uso
const cursos = await buscarCursos('ICS2123');
console.log(cursos);
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

# Uso
cursos = buscar_cursos('ICS2123')
print(cursos)
```

## 📄 Licencia

MIT License - Proyecto open-source para la comunidad UC.

## 👤 Autor

Desarrollado para facilitar la organización de horarios universitarios.
