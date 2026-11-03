'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

import { PageHeader } from '@/components/page/page-header'
import { UserProfileForm } from '@/components/profile/user-profile-form'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ApiError, apiFetch } from '@/lib/api'
import { useT } from '@/lib/i18n'
import { normalizeProfileMeta, normalizeUserProfileFieldsConfig, type UserProfileFieldsConfig, type UserProfileMeta } from '@/lib/user-profile-fields'
import { useAuth } from '@/hooks/useAuth'

type MineProfileResponse = {
  profile?: Record<string, unknown>
  profileMeta?: UserProfileMeta
  profileSchema?: UserProfileFieldsConfig
  mustCompleteProfile?: boolean
}

export default function ProfileRequiredPage() {
  const t = useT()
  const { session, setSession } = useAuth()
  const router = useRouter()

  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [profileForm, setProfileForm] = useState<Record<string, unknown>>({})
  const [profileSchema, setProfileSchema] = useState<UserProfileFieldsConfig>(normalizeUserProfileFieldsConfig(null))
  const [profileMeta, setProfileMeta] = useState<UserProfileMeta>(normalizeProfileMeta(null))

  useEffect(() => {
    if (!session) return
    let ignore = false

    const load = async () => {
      setLoading(true)
      try {
        const mine = await apiFetch<MineProfileResponse>('/api/v1/auth/mine', { session })
        if (ignore) return
        if (!mine.mustCompleteProfile) {
          setSession({
            ...session,
            mustCompleteProfile: false,
          })
          router.replace('/welcome')
          return
        }
        setProfileForm(mine.profile || {})
        setProfileMeta(normalizeProfileMeta(mine.profileMeta))
        setProfileSchema(normalizeUserProfileFieldsConfig(mine.profileSchema))
      } catch (err) {
        if (!ignore) {
          toast.error(err instanceof ApiError ? err.message : t('system.personal.profileLoadFailed'))
        }
      } finally {
        if (!ignore) setLoading(false)
      }
    }

    void load()
    return () => {
      ignore = true
    }
  }, [router, session, setSession, t])

  if (!session) return null

  return (
    <div className="grid gap-4">
      <PageHeader
        title={t('system.personal.completeProfileTitle')}
        description={t('system.personal.completeProfileDescription')}
      />
      <Card>
        <CardContent className="grid gap-4">
          <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
            {t('system.personal.missingFields').replace(
              '{fields}',
              (profileMeta.missingRequiredKeys || []).join(', ') || t('system.personal.checkRequiredProfile'),
            )}
          </div>

          <UserProfileForm
            config={profileSchema}
            value={profileForm}
            onChange={setProfileForm}
            disabled={loading || saving}
            className="grid-cols-1 gap-3"
          />

          <div className="flex flex-wrap gap-2">
            <Button
              disabled={loading || saving}
              onClick={async () => {
                setSaving(true)
                try {
                  const res = await apiFetch<MineProfileResponse>('/api/v1/auth/profile', {
                    method: 'PUT',
                    session,
                    body: JSON.stringify({
                      profile: profileForm,
                    }),
                  })

                  const mustCompleteProfile = Boolean(res.mustCompleteProfile)
                  setProfileForm(res.profile || {})
                  setProfileMeta(normalizeProfileMeta(res.profileMeta))
                  setProfileSchema(normalizeUserProfileFieldsConfig(res.profileSchema))
                  setSession({
                    ...session,
                    mustCompleteProfile,
                  })

                  if (mustCompleteProfile) {
                    toast.error(t('system.personal.requiredProfileIncomplete'))
                    return
                  }

                  toast.success(t('system.personal.profileCompleted'))
                  router.replace('/welcome')
                } catch (err) {
                  toast.error(err instanceof ApiError ? err.message : t('system.personal.profileSaveFailed'))
                } finally {
                  setSaving(false)
                }
              }}
            >
              {saving ? t('system.common.submitting') : t('system.personal.submitProfile')}
            </Button>
            <Button variant="outline" onClick={() => router.push('/personal/settings')} disabled={loading || saving}>
              {t('system.personal.openSettings')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
