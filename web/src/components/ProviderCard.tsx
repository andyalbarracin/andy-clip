import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

import { api, ApiError } from "../lib/api";
import type { AiProvider } from "../types/api";
import { Button, Choice, Field, StatusTag, TextInput } from "./ui";
import "./ProviderCard.css";

const CUSTOM = "__custom__";

interface Props {
  provider: AiProvider;
  isDefault: boolean;
  onMakeDefault: () => void;
}

/**
 * Un proveedor de IA: estado, credencial, modelo y las dos acciones que sí
 * salen a la red — y solo cuando la persona las pulsa.
 *
 * La API key nunca vuelve del backend: mientras está guardada mostramos la
 * versión enmascarada y el campo queda vacío, listo para reemplazarla.
 */
export function ProviderCard({ provider, isDefault, onMakeDefault }: Props) {
  const queryClient = useQueryClient();

  const [draftKey, setDraftKey] = useState("");
  const [visible, setVisible] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [models, setModels] = useState<string[] | null>(null);
  const [customModel, setCustomModel] = useState("");
  const [usingCustom, setUsingCustom] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["ai-settings"] });
    queryClient.invalidateQueries({ queryKey: ["system-status"] });
    queryClient.invalidateQueries({ queryKey: ["home"] });
  };

  const reportError = (error: ApiError) =>
    setResult({ ok: false, message: error.message });

  const saveKey = useMutation({
    mutationFn: () => api.saveApiKey(provider.id, draftKey.trim()),
    onSuccess: () => {
      setDraftKey("");
      setVisible(false);
      setResult({ ok: true, message: "Guardamos la clave." });
      refresh();
    },
    onError: reportError,
  });

  const removeKey = useMutation({
    mutationFn: () => api.deleteApiKey(provider.id),
    onSuccess: () => {
      setConfirmingDelete(false);
      setResult(null);
      refresh();
    },
    onError: reportError,
  });

  const saveModel = useMutation({
    mutationFn: (model: string) =>
      api.updateSettings({ ai: { [`${provider.id}_model`]: model } }),
    onSuccess: () => {
      setResult({ ok: true, message: "Guardamos el modelo." });
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      refresh();
    },
    onError: reportError,
  });

  const testConnection = useMutation({
    mutationFn: () => api.testProvider(provider.id),
    onSuccess: (data) => {
      setResult({ ok: data.ok, message: data.message });
      if (data.models.length > 0) setModels(data.models);
    },
    onError: reportError,
  });

  const refreshModels = useMutation({
    mutationFn: () => api.refreshModels(provider.id),
    onSuccess: (data) => {
      setModels(data.models);
      setResult({
        ok: true,
        message: `Encontramos ${data.models.length} modelos disponibles.`,
      });
    },
    onError: reportError,
  });

  const available = models ?? provider.suggested_models ?? [];
  const modelList = provider.model && !available.includes(provider.model)
    ? [provider.model, ...available]
    : available;

  const busy =
    saveKey.isPending ||
    removeKey.isPending ||
    testConnection.isPending ||
    refreshModels.isPending;

  return (
    <article className="provider">
      <header className="provider__head">
        <div className="provider__title">
          <h3>{provider.label}</h3>
          <StatusTag status={provider.configured ? "configured" : "not_configured"} />
          {provider.key_source === "env" && (
            <span className="source-tag">viene de {provider.env_var}</span>
          )}
        </div>

        {provider.testable &&
          (isDefault ? (
            <span className="provider__default">Proveedor predeterminado</span>
          ) : (
            <Button size="sm" variant="ghost" onClick={onMakeDefault}>
              Usar por defecto
            </Button>
          ))}
      </header>

      <div className="provider__body">
        <Field
          label="API key"
          htmlFor={`key-${provider.id}`}
          hint={
            provider.configured
              ? `Guardada como ${provider.masked_key}. Escribí una nueva para reemplazarla.`
              : "La guardamos en tu equipo, fuera del control de versiones. Nunca vuelve al navegador."
          }
        >
          <div className="provider__key">
            <span className="provider__key-field">
              <TextInput
                id={`key-${provider.id}`}
                type={visible ? "text" : "password"}
                value={draftKey}
                onChange={setDraftKey}
                placeholder={provider.configured ? provider.masked_key ?? "" : "Pegá tu API key"}
                isMonospaced
              />
              <button
                type="button"
                className="provider__eye"
                onClick={() => setVisible((current) => !current)}
                aria-label={visible ? "Ocultar la clave" : "Mostrar la clave"}
              >
                {visible ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </span>
            <Button
              variant="primary"
              onClick={() => saveKey.mutate()}
              disabled={!draftKey.trim() || busy}
              loading={saveKey.isPending}
            >
              Guardar
            </Button>
          </div>
        </Field>

        {provider.testable && (
          <Field
            label="Modelo"
            htmlFor={`model-${provider.id}`}
            hint="Podés elegir uno de la lista o escribir el nombre exacto de otro."
          >
            <div className="provider__model">
              <Choice
                id={`model-${provider.id}`}
                value={usingCustom ? CUSTOM : provider.model ?? ""}
                onChange={(value) => {
                  if (value === CUSTOM) {
                    setUsingCustom(true);
                    setCustomModel(provider.model ?? "");
                    return;
                  }
                  setUsingCustom(false);
                  saveModel.mutate(value);
                }}
                options={[
                  ...modelList.map((model) => ({ value: model, label: model })),
                  { value: CUSTOM, label: "Otro modelo…" },
                ]}
              />

              <Button
                onClick={() => refreshModels.mutate()}
                disabled={!provider.configured || busy}
                loading={refreshModels.isPending}
              >
                Actualizar modelos
              </Button>
            </div>
          </Field>
        )}

        {usingCustom && (
          <form
            className="provider__custom"
            onSubmit={(event) => {
              event.preventDefault();
              saveModel.mutate(customModel.trim());
              setUsingCustom(false);
            }}
          >
            <label className="sr-only" htmlFor={`custom-${provider.id}`}>
              Nombre del modelo
            </label>
            <TextInput
              id={`custom-${provider.id}`}
              value={customModel}
              onChange={setCustomModel}
              placeholder="por ejemplo, gpt-4.1-mini"
              isMonospaced
              autoFocus
            />
            <Button variant="primary" type="submit" disabled={!customModel.trim()}>
              Usar este modelo
            </Button>
            <Button type="button" onClick={() => setUsingCustom(false)}>
              Cancelar
            </Button>
          </form>
        )}
      </div>

      <footer className="provider__foot">
        {provider.testable && (
          <Button
            onClick={() => testConnection.mutate()}
            disabled={busy}
            loading={testConnection.isPending}
          >
            Probar conexión
          </Button>
        )}

        {provider.configured && provider.key_source === "app" && !confirmingDelete && (
          <Button variant="ghost" size="sm" onClick={() => setConfirmingDelete(true)}>
            Eliminar clave
          </Button>
        )}

        {confirmingDelete && (
          <span className="provider__confirm">
            ¿Eliminar la clave de {provider.label}?
            <Button
              variant="danger"
              size="sm"
              onClick={() => removeKey.mutate()}
              loading={removeKey.isPending}
            >
              Eliminar
            </Button>
            <Button size="sm" onClick={() => setConfirmingDelete(false)}>
              Cancelar
            </Button>
          </span>
        )}

        {result && (
          <p
            className={`provider__result provider__result--${result.ok ? "ok" : "bad"}`}
            role="status"
          >
            {result.message}
          </p>
        )}
      </footer>
    </article>
  );
}
