<template>

  <div class="images-page" v-loading="imagesLoading">

    <div class="page-header">

      <h2>图片管理 - {{ property?.title }}</h2>

      <el-button text :icon="ArrowLeft" @click="$router.back()">清空</el-button>

    </div>



    <!-- Upload area -->

    <el-card shadow="never" class="upload-card">

      <el-upload

        v-model:file-list="fileList"

        :auto-upload="false"

        list-type="picture-card"

        multiple

        :limit="maxLimit"

        :accept="'image/jpeg,image/png,image/webp'"

        :on-exceed="handleExceed"

        :before-upload="beforeUpload"

        drag

      >

        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>

        <div class="el-upload__text">

          将文件拖到此处，或 <em>点击上传</em>

        </div>

        <template #tip>

          <div class="el-upload__tip">

            仅支持 JPG/PNG/WebP 格式，单文件不超过 5MB，当前 {{ images.length }}/10 张

          </div>

        </template>

      </el-upload>

      <div v-if="fileList.length > 0" class="upload-actions">

        <el-button type="primary" :loading="uploading" @click="handleUpload">

          ?? {{ fileList.length }} ???

        </el-button>

        <el-button @click="fileList = []">清空</el-button>

      </div>

    </el-card>



    <!-- Image grid -->

    <el-card shadow="never" class="grid-card" v-if="images.length > 0">

      <el-row :gutter="16">

        <el-col

          v-for="img in sortedImages"

          :key="img.id"

          :xs="12"

          :sm="8"

          :md="6"

          :lg="4"

          class="image-item"

        >

          <div class="image-wrapper" :class="{ primary: img.is_primary }">

            <el-image

              :src="`/api/v1/uploads/${img.filename}`"

              fit="cover"

              class="property-image"

              :preview-src-list="[`/api/v1/uploads/${img.filename}`]"

              preview-teleported

            />

            <div class="image-overlay">

              <el-tag v-if="img.is_primary" type="danger" size="small" class="primary-tag">??</el-tag>

              <div class="image-actions">

                <el-button

                  v-if="!img.is_primary"

                  size="small"

                  circle

                  type="warning"

                  :icon="Star"

                  title="设为封面"

                  @click="handleSetPrimary(img.id)"

                />

                <el-popconfirm

                  title="确认删除该图片？"

                  @confirm="handleDelete(img.id)"

                >

                  <template #reference>

                    <el-button size="small" circle type="danger" :icon="Delete" title="??" />

                  </template>

                </el-popconfirm>

              </div>

            </div>

          </div>

        </el-col>

      </el-row>

    </el-card>



    <el-empty v-else-if="!imagesLoading" description="暂无图片" />

  </div>

</template>



<script setup lang="ts">

import { ref, computed, onMounted } from 'vue'

import { useRoute } from 'vue-router'

import { ElMessage } from 'element-plus'

import { ArrowLeft, UploadFilled, Star, Delete } from '@element-plus/icons-vue'

import type { UploadFile, UploadRawFile } from 'element-plus'

import { usePropertyStore } from '@/stores/property'

import { storeToRefs } from 'pinia'



const route = useRoute()

const propertyStore = usePropertyStore()

const { currentProperty: property, propertyImages: images, imagesLoading } = storeToRefs(propertyStore)



const fileList = ref<UploadFile[]>([])

const uploading = ref(false)

const maxLimit = computed(() => Math.max(0, 10 - images.value.length))



const sortedImages = computed(() =>

  [...images.value].sort((a, b) => {

    if (a.is_primary) return -1

    if (b.is_primary) return 1

    return a.sort_order - b.sort_order

  })

)



function handleExceed() {

  ElMessage.warning('最多上传 10 张图片')

}



function beforeUpload(file: UploadRawFile) {

  const isValidType = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)

  if (!isValidType) {

    ElMessage.error('仅支持 JPG、PNG、WebP 格式')

    return false

  }

  const isValidSize = file.size <= 5 * 1024 * 1024

  if (!isValidSize) {

    ElMessage.error('图片大小不能超过 5MB')

    return false

  }

  return true

}



async function handleUpload() {

  if (fileList.value.length === 0) return

  uploading.value = true

  try {

    const propertyId = Number(route.params.id)

    const rawFiles = fileList.value.map((f) => f.raw!).filter(Boolean)

    await propertyStore.uploadImages(propertyId, rawFiles)

    fileList.value = []

    ElMessage.success(`成功上传 ${rawFiles.length} 张图片`)

  } catch {

    // handled by interceptor

  } finally {

    uploading.value = false

  }

}



async function handleDelete(imageId: number) {

  try {

    const propertyId = Number(route.params.id)

    await propertyStore.deleteImage(propertyId, imageId)

    ElMessage.success('设置成功')

  } catch {

    // handled by interceptor

  }

}



async function handleSetPrimary(imageId: number) {

  try {

    const propertyId = Number(route.params.id)

    await propertyStore.setPrimaryImage(propertyId, imageId)

    ElMessage.success('设置成功')

  } catch {

    // handled by interceptor

  }

}



onMounted(() => {

  const id = Number(route.params.id)

  if (id) {

    propertyStore.fetchById(id)

    propertyStore.fetchImages(id)

  }

})

</script>



<style scoped>

.images-page {

  max-width: 1000px;

  margin: 0 auto;

}



.page-header {

  display: flex;

  justify-content: space-between;

  align-items: center;

  margin-bottom: 20px;

}



.page-header h2 {

  font-size: 22px;

  color: #303133;

}



.upload-card {

  margin-bottom: 20px;

}



.upload-actions {

  margin-top: 16px;

  display: flex;

  gap: 12px;

}



.grid-card {

  margin-bottom: 20px;

}



.image-item {

  margin-bottom: 16px;

}



.image-wrapper {

  position: relative;

  border-radius: 8px;

  overflow: hidden;

  border: 3px solid transparent;

  transition: border-color 0.2s;

}



.image-wrapper.primary {

  border-color: #f56c6c;

}



.property-image {

  width: 100%;

  aspect-ratio: 4 / 3;

  display: block;

}



.image-overlay {

  position: absolute;

  top: 0;

  left: 0;

  right: 0;

  bottom: 0;

  background: rgba(0, 0, 0, 0.3);

  opacity: 0;

  transition: opacity 0.2s;

  display: flex;

  align-items: center;

  justify-content: center;

}



.image-wrapper:hover .image-overlay {

  opacity: 1;

}



.primary-tag {

  position: absolute;

  top: 8px;

  right: 8px;

}



.image-actions {

  display: flex;

  gap: 8px;

}

</style>

