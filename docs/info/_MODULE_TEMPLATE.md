# Plantilla de documentación de módulo (`_MODULE_TEMPLATE.md`)

Usa esta plantilla al crear un nuevo `.md` en `docs/info/` (eliminando este bloque introductorio). No inventes apartados si no aplican: indícalo brevemente o márcalo como `⚠️ sin verificar` hasta contrastarlo con el código.

---

# `<nombre-del-modulo>`

> Ficheros cubiertos: [`../../src/...`](../../src/)

## 1. Qué hace y qué NO hace

- **Hace:** ...
- **NO hace:** ...

## 2. Modelo de datos

Tablas, DTOs, enumeraciones o estructuras de estado que define o gestiona el módulo.

## 3. Flujos principales

Secuencia paso a paso de las operaciones clave.

## 4. Puntos de entrada (con auth, permisos y límites)

Funciones públicas, clases, comandos o callbacks expuestos; quién puede invocarlos y qué validaciones o límites aplican.

## 5. Dependencias en ambos sentidos

- **Depende de:** módulos internos, librerías o APIs externas que consume.
- **Consumido por:** módulos que importan o llaman a este módulo.

## 6. Configuración (variables, valor por defecto y efecto)

| Variable (`.env`) | Atributo `Settings` | Valor por defecto | Efecto |
|---|---|---|---|
| ... | ... | ... | ... |

## 7. Trampas conocidas

Casos límite, acoplamientos sutiles, orden obligatorio de llamadas o detalles que pueden causar regresiones.

## 8. Tests que lo cubren

- [`../../tests/...`](../../tests/) — qué escenarios verifica realmente.

## 9. Pendiente real

Trabajo o mejoras verificadas como ausentes en el código actual (no deseos genéricos).

---

> Creado: 2026-11-20 · Última revisión: 2026-11-20
