import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.daweiba.gork"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.daweiba.gork"
        minSdk = 31
        targetSdk = 35
        versionCode = 6
        versionName = "0.1.5-dev"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin { compilerOptions { jvmTarget.set(JvmTarget.JVM_17) } }

dependencies {
    implementation("androidx.webkit:webkit:1.17.1")
    testImplementation("junit:junit:4.13.2")
}

val syncSharedAvatarAssets by tasks.registering(Exec::class) {
    val python = System.getenv("PYTHON") ?: if (System.getProperty("os.name").startsWith("Windows")) "python" else "python3"
    workingDir(rootProject.projectDir)
    commandLine(python, "tools/export_shared_assets.py")
}

tasks.named("preBuild") { dependsOn(syncSharedAvatarAssets) }
