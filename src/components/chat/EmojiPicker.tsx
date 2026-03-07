import { useState, useRef, useEffect } from 'react'
import { Search, X } from 'lucide-react'

const EMOJI_CATEGORIES = [
  {
    id: 'frequent',
    label: '⏱️',
    title: 'Frequently Used',
    emojis: ['👋', '😂', '❤️', '🔥', '👍', '😊', '🎉', '✨', '😭', '🥺', '💀', '🤣', '😍', '🙏', '😁', '💯'],
  },
  {
    id: 'smileys',
    label: '😀',
    title: 'Smileys & People',
    emojis: [
      '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗',
      '😚', '😙', '🥲', '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔', '🫡', '🤐', '🤨',
      '😐', '😑', '😶', '🫥', '😏', '😒', '🙄', '😬', '🤥', '😌', '😔', '😪', '🤤', '😴', '😷', '🤒',
      '🤕', '🤢', '🤮', '🥴', '😵', '🤯', '🥳', '🥸', '😎', '🤓', '🧐', '😕', '🫤', '😟', '🙁', '😮',
      '😯', '😲', '😳', '🥺', '🥹', '😦', '😧', '😨', '😰', '😥', '😢', '😭', '😱', '😖', '😣', '😞',
      '😓', '😩', '😫', '🥱', '😤', '😡', '😠', '🤬', '😈', '👿', '💀', '☠️', '💩', '🤡', '👹', '👺',
      '👻', '👽', '👾', '🤖', '🎃', '😺', '😸', '😹', '😻', '😼', '😽', '🙀', '😿', '😾',
      '👋', '🤚', '🖐️', '✋', '🖖', '🫱', '🫲', '🫳', '🫴', '👌', '🤌', '🤏', '✌️', '🤞', '🫰', '🤟',
      '🤘', '🤙', '👈', '👉', '👆', '🖕', '👇', '🫵', '☝️', '👍', '👎', '✊', '👊', '🤛', '🤜', '👏',
      '🙌', '🫶', '👐', '🤲', '🤝', '🙏', '✍️', '💅', '🤳', '💪', '🦾', '🦿',
    ],
  },
  {
    id: 'nature',
    label: '🐾',
    title: 'Animals & Nature',
    emojis: [
      '🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐻‍❄️', '🐨', '🐯', '🦁', '🐮', '🐷', '🐸', '🐵',
      '🙈', '🙉', '🙊', '🐔', '🐧', '🐦', '🐤', '🪿', '🦆', '🦅', '🦉', '🐺', '🐗', '🐴', '🦄', '🐝',
      '🪱', '🐛', '🦋', '🐌', '🐞', '🐜', '🪰', '🪲', '🪳', '🐢', '🐍', '🦎', '🦖', '🦕', '🐙', '🦑',
      '🦐', '🦞', '🦀', '🪼', '🐡', '🐠', '🐟', '🐬', '🐳', '🐋', '🦈', '🐊',
      '🌵', '🎄', '🌲', '🌳', '🌴', '🪵', '🌱', '🌿', '☘️', '🍀', '🎍', '🪴', '🎋', '🍃', '🍂', '🍁',
      '🌾', '🌺', '🌻', '🌹', '🥀', '🌷', '🪻', '🌼', '🌸', '💐', '🍄', '🌰', '🐚', '🪸',
    ],
  },
  {
    id: 'food',
    label: '🍔',
    title: 'Food & Drink',
    emojis: [
      '🍇', '🍈', '🍉', '🍊', '🍋', '🍌', '🍍', '🥭', '🍎', '🍏', '🍐', '🍑', '🍒', '🍓', '🫐', '🥝',
      '🍅', '🫒', '🥥', '🥑', '🍆', '🥔', '🥕', '🌽', '🌶️', '🫑', '🥒', '🥬', '🥦', '🧄', '🧅', '🥜',
      '🫘', '🌰', '🫚', '🍞', '🥐', '🥖', '🫓', '🥨', '🥯', '🥞', '🧇', '🧀', '🍖', '🍗', '🥩', '🥓',
      '🍔', '🍟', '🍕', '🌭', '🥪', '🌮', '🌯', '🫔', '🥙', '🧆', '🥚', '🍳', '🥘', '🍲', '🫕', '🥣',
      '🥗', '🍿', '🧈', '🧂', '🥫', '🍱', '🍘', '🍙', '🍚', '🍛', '🍜', '🍝', '🍠', '🍢', '🍣', '🍤',
      '🍥', '🥮', '🍡', '🥟', '🥠', '🥡', '🦀', '🦞', '🦐', '🦑', '🦪',
      '🍦', '🍧', '🍨', '🍩', '🍪', '🎂', '🍰', '🧁', '🥧', '🍫', '🍬', '🍭', '🍮', '🍯',
      '🍼', '🥛', '☕', '🫖', '🍵', '🧃', '🥤', '🧋', '🍶', '🍺', '🍻', '🥂', '🍷', '🥃', '🍸', '🍹', '🧉', '🍾',
    ],
  },
  {
    id: 'activities',
    label: '⚽',
    title: 'Activities',
    emojis: [
      '⚽', '🏀', '🏈', '⚾', '🥎', '🎾', '🏐', '🏉', '🥏', '🎱', '🪀', '🏓', '🏸', '🏒', '🏑', '🥍',
      '🏏', '🪃', '🥅', '⛳', '🪁', '🏹', '🎣', '🤿', '🥊', '🥋', '🎽', '🛹', '🛼', '🛷', '⛸️', '🥌',
      '🎿', '⛷️', '🏂', '🪂', '🏋️', '🤼', '🤸', '🤺', '⛹️', '🧗', '🏇', '🚴', '🚵', '🎮', '🕹️', '🎲',
      '♟️', '🎯', '🎳', '🎪', '🎭', '🎨', '🎬', '🎤', '🎧', '🎼', '🎹', '🥁', '🪘', '🎷', '🎺', '🪗',
      '🎸', '🪕', '🎻', '🪈', '🎬', '🏆', '🥇', '🥈', '🥉', '🏅', '🎖️', '🏵️', '🎗️', '🎫', '🎟️', '🎪',
    ],
  },
  {
    id: 'travel',
    label: '🚗',
    title: 'Travel & Places',
    emojis: [
      '🚗', '🚕', '🚙', '🚌', '🚎', '🏎️', '🚓', '🚑', '🚒', '🚐', '🛻', '🚚', '🚛', '🚜', '🛵', '🏍️',
      '🛺', '🚲', '🛴', '🛹', '🚁', '✈️', '🛩️', '🚀', '🛸', '🚢', '⛵', '🚤', '🛥️', '⛴️', '🛳️',
      '🏠', '🏡', '🏢', '🏣', '🏤', '🏥', '🏦', '🏨', '🏩', '🏪', '🏫', '🏬', '🏯', '🏰', '💒', '🗼',
      '🗽', '⛪', '🕌', '🛕', '🕍', '⛩️', '🕋', '⛲', '⛺', '🌁', '🌃', '🏙️', '🌄', '🌅', '🌆', '🌇',
      '🌉', '🎠', '🛝', '🎡', '🎢', '🌋', '🗻', '🏔️', '⛰️', '🏕️', '🏖️', '🏜️', '🏝️', '🏞️',
    ],
  },
  {
    id: 'objects',
    label: '💡',
    title: 'Objects',
    emojis: [
      '⌚', '📱', '💻', '⌨️', '🖥️', '🖨️', '🖱️', '💽', '💾', '💿', '📀', '🎥', '📷', '📹', '📼', '🔍',
      '🔎', '🕯️', '💡', '🔦', '🏮', '📔', '📕', '📖', '📗', '📘', '📙', '📚', '📓', '📒', '📃', '📜',
      '📄', '📰', '🗞️', '🏷️', '💰', '🪙', '💴', '💵', '💶', '💷', '💸', '💳', '🧾', '✉️', '📧', '📨',
      '📩', '📤', '📥', '📦', '📫', '📪', '📬', '📭', '🗳️', '✏️', '✒️', '🖋️', '🖊️', '🖌️', '🖍️',
      '📝', '📁', '📂', '🗂️', '📅', '📆', '🗒️', '🗓️', '📇', '📈', '📉', '📊', '📋', '📌', '📍', '📎',
      '🖇️', '📏', '📐', '✂️', '🗃️', '🗄️', '🗑️', '🔒', '🔓', '🔏', '🔐', '🔑', '🗝️',
    ],
  },
  {
    id: 'symbols',
    label: '❤️',
    title: 'Symbols',
    emojis: [
      '❤️', '🩷', '🧡', '💛', '💚', '💙', '🩵', '💜', '🖤', '🩶', '🤍', '🤎', '💔', '❤️‍🔥', '❤️‍🩹', '❣️',
      '💕', '💞', '💓', '💗', '💖', '💘', '💝', '💟', '☮️', '✝️', '☪️', '🕉️', '☸️', '✡️', '🔯', '🕎',
      '☯️', '☦️', '🛐', '⛎', '♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓',
      '🆔', '⚛️', '🉑', '☢️', '☣️', '📴', '📳', '🈶', '🈚', '🈸', '🈺', '🈷️', '✴️', '🆚',
      '💮', '🉐', '㊙️', '㊗️', '🈴', '🈵', '🈹', '🈲', '🅰️', '🅱️', '🆎', '🆑', '🅾️', '🆘', '❌', '⭕',
      '🛑', '⛔', '📛', '🚫', '💯', '💢', '♨️', '🚷', '🚱', '🔞', '📵', '🚳', '❗', '❕', '❓', '❔',
      '‼️', '⁉️', '💤', '♻️', '✅', '☑️', '✔️', '❎', '➕', '➖', '➗', '✖️', '♾️', '💲',
    ],
  },
  {
    id: 'flags',
    label: '🏁',
    title: 'Flags',
    emojis: [
      '🏁', '🚩', '🎌', '🏴', '🏳️', '🏳️‍🌈', '🏳️‍⚧️', '🏴‍☠️',
      '🇺🇸', '🇬🇧', '🇯🇵', '🇰🇷', '🇨🇳', '🇩🇪', '🇫🇷', '🇪🇸',
      '🇮🇹', '🇧🇷', '🇷🇺', '🇮🇳', '🇦🇺', '🇨🇦', '🇲🇽', '🇦🇷',
      '🇹🇭', '🇻🇳', '🇮🇩', '🇵🇭', '🇳🇱', '🇵🇱', '🇹🇷', '🇺🇦',
      '🇸🇪', '🇳🇴', '🇫🇮', '🇩🇰', '🇨🇭', '🇦🇹', '🇧🇪', '🇵🇹',
    ],
  },
] as const

interface EmojiPickerProps {
  onSelect: (emoji: string) => void
  onClose: () => void
}

export function EmojiPicker({ onSelect, onClose }: EmojiPickerProps) {
  const [activeCategory, setActiveCategory] = useState('frequent')
  const [searchQuery, setSearchQuery] = useState('')
  const pickerRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)

  // Focus search on open
  useEffect(() => {
    searchRef.current?.focus()
  }, [])

  // Close on Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  // Get filtered emojis
  const getFilteredEmojis = () => {
    if (!searchQuery.trim()) {
      return EMOJI_CATEGORIES.find(c => c.id === activeCategory)?.emojis || []
    }
    // Search across all categories (deduplicated)
    const all = new Set<string>()
    for (const cat of EMOJI_CATEGORIES) {
      for (const emoji of cat.emojis) {
        all.add(emoji)
      }
    }
    return Array.from(all)
  }

  const filteredEmojis = getFilteredEmojis()

  // Scroll to category section
  const handleCategoryClick = (categoryId: string) => {
    setSearchQuery('')
    setActiveCategory(categoryId)
    gridRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div
      ref={pickerRef}
      className="absolute bottom-full mb-2 left-0 bg-background border border-border rounded-xl shadow-xl z-50 w-[320px] overflow-hidden"
    >
      {/* Header with search */}
      <div className="p-2 border-b border-border">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            ref={searchRef}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search emoji..."
            className="w-full bg-secondary/50 border border-border rounded-lg pl-8 pr-8 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex border-b border-border px-1">
        {EMOJI_CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            onClick={() => handleCategoryClick(cat.id)}
            title={cat.title}
            className={`flex-1 py-1.5 text-center text-sm transition-colors hover:bg-secondary rounded-t-md ${
              activeCategory === cat.id && !searchQuery
                ? 'bg-secondary/80 border-b-2 border-primary'
                : ''
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Emoji grid */}
      <div ref={gridRef} className="h-[200px] overflow-y-auto p-2">
        {!searchQuery && (
          <p className="text-xs text-muted-foreground px-1 pb-1.5 font-medium">
            {EMOJI_CATEGORIES.find(c => c.id === activeCategory)?.title}
          </p>
        )}
        {searchQuery && filteredEmojis.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            No emoji found
          </div>
        ) : (
          <div className="grid grid-cols-8 gap-0.5">
            {filteredEmojis.map((emoji, idx) => (
              <button
                key={`${emoji}-${idx}`}
                onClick={() => onSelect(emoji)}
                className="w-9 h-9 flex items-center justify-center text-xl rounded-lg hover:bg-secondary transition-colors"
                title={emoji}
              >
                {emoji}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
