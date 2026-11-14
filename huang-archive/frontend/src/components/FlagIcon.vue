<script setup>
defineProps({
  code: { type: String, required: true }, // cn | us | ru
  size: { type: Number, default: 18 },
})
</script>

<template>
  <span
    class="flag-icon inline-block overflow-hidden rounded-[2px] border border-black/10 shrink-0"
    :style="{ width: size + 'px', height: Math.round(size * 0.72) + 'px' }"
    aria-hidden="true"
  >
    <!-- CN -->
    <svg v-if="code === 'cn'" viewBox="0 0 30 20" class="w-full h-full" xmlns="http://www.w3.org/2000/svg">
      <rect width="30" height="20" fill="#DE2910" />
      <polygon fill="#FFDE00" points="5,2.5 5.9,5.2 8.8,5.2 6.45,6.9 7.35,9.6 5,7.9 2.65,9.6 3.55,6.9 1.2,5.2 4.1,5.2" />
    </svg>
    <!-- US -->
    <svg v-else-if="code === 'us'" viewBox="0 0 30 20" class="w-full h-full" xmlns="http://www.w3.org/2000/svg">
      <rect width="30" height="20" fill="#fff" />
      <rect y="0" width="30" height="1.54" fill="#B22234" />
      <rect y="3.08" width="30" height="1.54" fill="#B22234" />
      <rect y="6.15" width="30" height="1.54" fill="#B22234" />
      <rect y="9.23" width="30" height="1.54" fill="#B22234" />
      <rect y="12.31" width="30" height="1.54" fill="#B22234" />
      <rect y="15.38" width="30" height="1.54" fill="#B22234" />
      <rect y="18.46" width="30" height="1.54" fill="#B22234" />
      <rect width="12" height="10.77" fill="#3C3B6E" />
    </svg>
    <!-- RU -->
    <svg v-else viewBox="0 0 30 20" class="w-full h-full" xmlns="http://www.w3.org/2000/svg">
      <rect width="30" height="6.67" y="0" fill="#fff" />
      <rect width="30" height="6.67" y="6.67" fill="#0039A6" />
      <rect width="30" height="6.66" y="13.34" fill="#D52B1E" />
    </svg>
  </span>
</template>
