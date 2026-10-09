# Lluvias CABA

Registro diario de la lluvia caída en la Ciudad de Buenos Aires, tomado de dos estaciones del
Servicio Meteorológico Nacional:

| Estación | Indicativo OMM |
|---|---|
| Buenos Aires – Observatorio Central (Villa Ortúzar) | 87585 |
| Aeroparque Jorge Newbery | 87582 |

Todos los días a las 10:40 (hora argentina) GitHub corre el programa, descarga los partes
meteorológicos de las últimas 24 horas, calcula la lluvia del día y la agrega a la base de datos.
No necesitás tener la computadora prendida ni pagar nada.

---

## Cómo funciona, en dos párrafos

El SMN no publica la lluvia diaria en un archivo abierto. Lo que sí hacen todas sus estaciones es
enviar, cada 3 horas, un **parte SYNOP** (el formato estándar de la Organización Meteorológica
Mundial) con temperatura, viento, presión y lluvia acumulada. Esos partes se distribuyen por la red
mundial de la OMM y el sitio [Ogimet](https://www.ogimet.com) los archiva y permite consultarlos.
Este programa los descarga desde ahí: los números son las mediciones originales del SMN.

Con esos partes el programa arma el total del **día pluviométrico**, que va de las 9:00 de un día
a las 9:00 del siguiente (es la convención usual en Argentina: el pluviómetro se lee a las 9 h).
Por ejemplo, la fila con fecha `2026-10-08` es la lluvia caída entre las 9 h del 8 y las 9 h del 9
de octubre.

---

## Paso a paso para ponerlo en marcha

Tiempo estimado: 15 minutos. Todo se hace desde el navegador.

### Paso 1. Crear una cuenta en GitHub

Si no tenés, entrá a <https://github.com/signup> y creá una cuenta gratuita.

### Paso 2. Crear el repositorio

1. Arriba a la derecha, tocá el **+** y elegí **New repository**.
2. En **Repository name** escribí `lluvias-caba`.
3. Elegí **Public**. (Así las ejecuciones diarias y la página web son gratis sin límite. Si lo
   preferís privado también funciona, pero la página web del paso 7 requiere un plan pago.)
4. **No** marques "Add a README file" ni ninguna otra opción: el repositorio tiene que quedar vacío.
5. Tocá **Create repository**.

### Paso 3. Subir los archivos

1. Descomprimí el archivo `lluvias-caba.zip` en tu computadora.
2. **Hacé visibles los archivos ocultos**, porque la carpeta `.github` (la que contiene las tareas
   automáticas) empieza con punto y el sistema la esconde:
   - **Windows:** en el Explorador de archivos, menú **Ver → Mostrar → Elementos ocultos**.
   - **Mac:** en el Finder, apretá **Cmd + Shift + .** (punto).
3. En la página del repositorio vacío, hacé clic en el link **uploading an existing file**.
4. Abrí la carpeta `lluvias-caba` que descomprimiste, seleccioná **todo su contenido** (no la
   carpeta en sí, sino lo que hay adentro: `.github`, `docs`, `lluvias`, `tests`, `config.json`,
   `README.md`, `.gitignore`) y arrastralo a la página.
5. Esperá a que termine de subir y tocá **Commit changes**.
6. **Verificá** que en la lista de archivos del repositorio aparezca la carpeta `.github`. Entrá y
   comprobá que adentro estén `workflows/diario.yml`, `workflows/historico.yml` y
   `workflows/diagnostico.yml`.

> **Si la carpeta `.github` no aparece:** tocá **Add file → Create new file**, escribí como nombre
> `.github/workflows/diario.yml` (al escribir las barras, GitHub crea las carpetas solo), pegá el
> contenido de ese archivo desde tu computadora (abrilo con el Bloc de notas o TextEdit) y tocá
> **Commit changes**. Repetí con `historico.yml` y `diagnostico.yml`.

### Paso 4. Darle permiso para guardar datos

El programa guarda la base de datos en el mismo repositorio, así que necesita permiso de escritura.

1. En el repositorio, entrá a **Settings** (pestaña de arriba, a la derecha).
2. En el menú de la izquierda: **Actions → General**.
3. Bajá hasta **Workflow permissions**, elegí **Read and write permissions** y tocá **Save**.

### Paso 5. Probar que llega a los datos

1. Entrá a la pestaña **Actions**. Si aparece un botón verde que dice
   *I understand my workflows, go ahead and enable them*, tocalo.
2. En la lista de la izquierda elegí **Diagnóstico** → botón **Run workflow** (a la derecha) →
   **Run workflow**.
3. Al minuto aparece una ejecución nueva. Entrá, abrí el trabajo **diagnostico** y desplegá el
   último paso. Tenés que ver algo así para cada estación:

   ```
   === Buenos Aires - Observatorio Central (Villa Ortúzar) (87585) — día pluviométrico 2026-10-08 ===
   2026-10-08 18:00Z  AAXX 08184 87585 32970 ...
         -> 6h iR=3: 0.0 mm
   ...
   Total: (0.0, False, '6h(iR=3) + 6h(iR=3) + 6h(iR=3) + 6h(iR=3)')
   ```

   Las líneas que empiezan con `AAXX` son los partes del SMN; las que tienen `->` son la lluvia que
   el programa leyó de cada parte. Si ves eso, todo funciona.

### Paso 6. Primera carga y carga del histórico

1. En **Actions**, elegí **Lluvia diaria** → **Run workflow**. Cuando termine (tilde verde), en el
   resumen de la ejecución vas a ver una tabla con la lluvia de los últimos días, y en el
   repositorio va a aparecer la carpeta `data` con la base de datos.
2. Para cargar el pasado, elegí **Carga histórica** → **Run workflow**, completá la fecha inicial
   (por ejemplo `2025-10-01`) y dejá la final vacía para llegar hasta ayer.
   - Tarda unos 20 minutos por año, porque hace pausas para no saturar el servidor de Ogimet.
   - Para varios años, conviene hacerlo de a uno (por ejemplo, primero `2024-01-01` a
     `2024-12-31`, después `2023-01-01` a `2023-12-31`). Si alguna tanda falla a la mitad, se
     puede volver a correr: lo ya guardado no se duplica.

A partir de acá no tenés que hacer nada más: **Lluvia diaria** se ejecuta sola todos los días.

### Paso 7 (opcional). Publicar la página con gráficos

1. **Settings → Pages**.
2. En **Build and deployment → Source** elegí **Deploy from a branch**.
3. En **Branch** elegí `main` y la carpeta `/docs`. Tocá **Save**.
4. En uno o dos minutos la página queda publicada en
   `https://TU-USUARIO.github.io/lluvias-caba/`. Se actualiza sola después de cada ejecución
   diaria. Tiene:
   - Selector de estación (se llena solo con las estaciones de `config.json`) y opción de
     comparar con otra.
   - Filtro de período: 30 días, 90 días, 12 meses, año en curso o todo el histórico.
   - Resumen del período: lluvia total, días con lluvia, día más lluvioso y último día.
   - Gráfico de lluvia por día (o por semana o mes en períodos largos), acumulado del año
     comparado con años anteriores y su promedio, y totales mes a mes contra el promedio.
   - Registro diario en tabla y descarga en CSV, del período elegido o de la base completa.

### Paso 8. Recibir un aviso si algo falla

GitHub manda un mail cuando una tarea programada termina con error. Para asegurarte:
en tu perfil (foto arriba a la derecha) → **Settings → Notifications → System → Actions**,
dejá marcado **Email** y **Only notify for failed workflows**.

El programa da error (y te llega el mail) si no pudo descargar nada o si pasaron 3 días seguidos
sin datos completos en ninguna estación. Un día suelto incompleto no es un error: se vuelve a
intentar automáticamente durante los 10 días siguientes, por si los partes llegan tarde.

---

## Dónde quedan los datos y cómo usarlos

| Archivo | Qué tiene |
|---|---|
| `data/lluvias.db` | Base SQLite con todo: estaciones, partes SYNOP crudos y lluvia diaria |
| `data/lluvias.csv` | La lluvia diaria en CSV, para abrir en Excel o Google Sheets |
| `docs/datos.json` | Los mismos datos en el formato que usa la página web |

**Columnas del CSV y de la tabla `lluvia_diaria`:**

| Columna | Significado |
|---|---|
| `fecha` | Día pluviométrico (de las 9 h de esa fecha a las 9 h del día siguiente) |
| `lluvia_mm` / `mm` | Milímetros. Vacío si no hay datos suficientes para ese día |
| `traza` | 1 si llovió menos de 0,1 mm (se registra como 0 mm con esta marca) |
| `completo` | 1 si los partes recibidos cubren las 24 horas |
| `metodo` | Qué partes se sumaron, por ejemplo `24h(7RRRR)` o `6h(6RRR-s1) + 6h(iR=3) + …` |
| `desde_utc`, `hasta_utc` | Período exacto en hora UTC (9 h en Argentina = 12 UTC) |

**Abrir el CSV en Google Sheets, siempre actualizado:** en una celda escribí

```
=IMPORTDATA("https://raw.githubusercontent.com/TU-USUARIO/lluvias-caba/main/data/lluvias.csv")
```

**Abrir la base SQLite:** descargá `data/lluvias.db` (botón de descarga en GitHub) y abrila con
[DB Browser for SQLite](https://sqlitebrowser.org), que es gratuito. Ejemplo de consulta, lluvia
mensual del Observatorio Central:

```sql
SELECT substr(fecha, 1, 7) AS mes, ROUND(SUM(mm), 1) AS total_mm, COUNT(*) AS dias
FROM lluvia_diaria
WHERE estacion = '87585' AND completo = 1
GROUP BY mes ORDER BY mes;
```

---

## Cómo se calcula el total diario

Cada parte SYNOP puede informar la lluvia de distintas maneras. Para cada día, el programa busca
la forma de cubrir exactamente las 24 horas usando la menor cantidad de partes, con este orden de
preferencia:

1. Grupo `7RRRR` (sección 3): total de 24 horas en décimas de milímetro. Es el más preciso.
2. Grupo `6RRRt` (sección 1 o 3): lluvia de un período de 1 a 24 horas, en milímetros.
3. Indicador `iR = 3`: la estación informa que no llovió en el período.

Si los partes que llegaron no alcanzan para cubrir las 24 horas, el día queda **vacío** (nunca se
inventa un cero) y se reintenta durante 10 días. Los partes originales quedan guardados en la tabla
`partes_synop`, así cualquier número se puede auditar o recalcular con
`python -m lluvias recalcular`.

**Diferencias posibles con las cifras que publica el SMN:** los partes SYNOP son datos en tiempo
real, sin la revisión de calidad que el SMN hace después para sus estadísticas oficiales. En la
gran mayoría de los días coinciden, pero puede haber diferencias puntuales.

---

## Agregar otras estaciones

Editá `config.json` en GitHub (tocá el archivo y después el lápiz) y agregá un bloque con el
indicativo OMM de la estación. Por ejemplo, para Ezeiza:

```json
{ "id": "87576", "nombre": "Ezeiza Aeropuerto", "corto": "Ezeiza", "lat": -34.82, "lon": -58.53 }
```

Los indicativos de las estaciones argentinas empiezan con 87 y se pueden buscar en Ogimet o en el
listado de estaciones de la OMM (OSCAR/Surface). Después corré **Carga histórica** para traer su
pasado. La página web muestra un gráfico por estación; con más de dos estaciones conviene
revisar los colores en `docs/index.html`.

---

## Si algo deja de funcionar

1. Corré **Diagnóstico** (paso 5) y mirá el resultado.
2. Si dice `Respuesta sin partes SYNOP` u otro error de descarga, Ogimet puede estar caído o
   haber cambiado su formato. Esperá un día; si sigue igual, el problema está en
   `lluvias/fuente.py`.
3. Si los partes aparecen pero sin líneas `->`, cambió la forma de informar la lluvia y hay que
   revisar `lluvias/synop.py`.
4. GitHub desactiva las tareas programadas de repositorios sin actividad por 60 días. Como este
   programa guarda datos todos los días, no debería pasar; si pasa, en **Actions → Lluvia diaria**
   aparece un botón **Enable workflow**.

## Correrlo en tu computadora (opcional)

Con Python 3.10 o más nuevo, sin instalar nada adicional, desde la carpeta del proyecto:

```
python -m lluvias diario
python -m lluvias historico --desde 2025-01-01
python -m unittest discover -s tests -t .
```
