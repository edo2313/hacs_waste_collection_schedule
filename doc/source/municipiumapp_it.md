# Municipium

Support for waste collection schedules of Italian municipalities using the [Municipium](https://www.municipiumapp.it/) app platform by Maggioli.

Not every municipality on Municipium publishes a waste collection calendar. If yours does not, the source will report it in the error message.

## Configuration via configuration.yaml

```yaml
waste_collection_schedule:
  sources:
    - name: municipiumapp_it
      args:
        municipality: MUNICIPALITY
        province: PROVINCE
        zone: ZONE
```

### Configuration Variables

**municipality**
*(string) (required)*

Name of your municipality as it appears in the Municipium app or  (e.g. `Bussolengo`). Case-insensitive.

**province**
*(string) (optional)*

Province name or two-letter code (e.g. `Verona` or `VR`). Only needed when multiple municipalities share the same name — the error message will list the possible provinces in that case.

**zone**
*(string) (optional)*

Name of the collection calendar/zone (e.g. `Utenza Pubblica - Zona A`). Can be omitted if the municipality has a single calendar. Partial names are accepted as long as they match a single calendar (e.g. `Zona A`).

## How to find your zone

1. Configure the source with only your `municipality`.
2. If the municipality has more than one collection calendar, the error message lists the available calendar names.
3. Set `zone` to the calendar that matches your area (a unique part of the name is enough).

Zone descriptions (which streets belong to which zone) are available in the Municipium app or on your municipality's website under the waste collection section.

## Example

```yaml
waste_collection_schedule:
  sources:
    - name: municipiumapp_it
      args:
        municipality: Bussolengo
        zone: Utenza Pubblica - Zona A
```

## Bin types and icons

Waste type names are defined by each municipality. Common types are mapped to icons:

| Waste type contains    | Icon                      |
| ---------------------- | ------------------------- |
| umido, organico        | `Icons.BIO_KITCHEN`       |
| carta, cartone         | `Icons.PAPER`             |
| plastica, lattine      | `Icons.PLASTIC_PACKAGING` |
| vetro                  | `Icons.GLASS`             |
| secco, indifferenziato | `Icons.GENERAL_WASTE`     |
| verde                  | `Icons.GARDEN`            |
| ingombranti            | `Icons.BULKY`             |
