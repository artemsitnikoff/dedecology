import type { CSSProperties } from 'react';
import {
  FileText,
  Settings,
  Search,
  X,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  ChevronUp,
  ArrowRight,
  ExternalLink,
  Funnel,
  Filter,
  Download,
  Trash2,
  Lock,
  Shield,
  User,
  Bell,
  LogOut,
  MapPin,
  Calendar,
  Clock,
  Image,
  RefreshCw,
  Plus,
  Save,
  Key,
  Mail,
  Copy,
  AlertCircle,
  Leaf,
  Map,
  List,
  Building2,
} from 'lucide-react';

/**
 * Центральная карта иконок поверх lucide-react.
 * Новые иконки добавляются расширением карты. IconName типизирован ключами карты,
 * поэтому неизвестное имя невозможно на этапе компиляции.
 */
const iconMap = {
  incidents: FileText,
  'file-text': FileText,
  settings: Settings,
  search: Search,
  x: X,
  check: Check,
  'chevron-down': ChevronDown,
  'chevron-right': ChevronRight,
  'chevron-left': ChevronLeft,
  'chevron-up': ChevronUp,
  chevD: ChevronDown,
  chevR: ChevronRight,
  chevL: ChevronLeft,
  chevU: ChevronUp,
  'arrow-right': ArrowRight,
  arrowRight: ArrowRight,
  open: ExternalLink,
  'external-link': ExternalLink,
  funnel: Funnel,
  filter: Filter,
  download: Download,
  trash: Trash2,
  lock: Lock,
  shield: Shield,
  user: User,
  bell: Bell,
  'log-out': LogOut,
  pin: MapPin,
  calendar: Calendar,
  clock: Clock,
  image: Image,
  refresh: RefreshCw,
  'refresh-cw': RefreshCw,
  plus: Plus,
  save: Save,
  key: Key,
  mail: Mail,
  copy: Copy,
  'alert-circle': AlertCircle,
  leaf: Leaf,
  map: Map,
  list: List,
  building: Building2,
} as const;

export type IconName = keyof typeof iconMap;

interface IconProps {
  name: IconName;
  size?: number;
  className?: string;
  color?: string;
  style?: CSSProperties;
}

export function Icon({ name, size = 20, className, color, style }: IconProps) {
  const IconComponent = iconMap[name];
  return <IconComponent size={size} className={className} color={color} style={style} />;
}
