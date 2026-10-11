export type LayoutMode = 'auto' | 'editorial' | 'structured' | 'spotlight';
export type ContentDensity = 'airy' | 'balanced' | 'compact';
export interface DesignStyle {
  name: string; category: string; description: string; family: string;
  primary: string; secondary: string; text: string; background: string;
}
export interface DesignCatalog {
  styles: DesignStyle[];
  illustrations?: { count:number; categories:string[] };
  layout_modes: { id: LayoutMode; name: string; description: string }[];
  densities: { id: ContentDensity; name: string; description: string }[];
}
