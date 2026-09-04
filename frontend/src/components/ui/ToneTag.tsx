import { Tag, type TagProps } from "antd";
import { useThemeMode } from "../../theme/ThemeProvider";
import { toneStyle, type Tone } from "./tone";

/** A tinted status pill whose text clears 7:1 in both themes. Use instead
 * of antd's `variant="filled"` tags, which fall below AA in dark mode. */
export function ToneTag({ tone, style, ...rest }: Omit<TagProps, "color" | "variant"> & { tone: Tone }) {
  const { mode } = useThemeMode();
  return <Tag {...rest} style={{ ...toneStyle(tone, mode), ...style }} />;
}
