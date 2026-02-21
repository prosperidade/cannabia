-- phpMyAdmin SQL Dump
-- version 5.1.2
-- https://www.phpmyadmin.net/
--
-- Host: localhost:3306
-- Tempo de geração: 21-Fev-2026 às 20:12
-- Versão do servidor: 5.7.24
-- versão do PHP: 8.3.1

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Banco de dados: `cannabia`
--

-- --------------------------------------------------------

--
-- Estrutura da tabela `ai_audit_logs`
--

CREATE TABLE `ai_audit_logs` (
  `id` int(11) NOT NULL,
  `patient_id` int(11) NOT NULL,
  `clinic_id` int(11) NOT NULL DEFAULT '1',
  `request_id` varchar(36) NOT NULL,
  `user_id` varchar(50) DEFAULT NULL,
  `endpoint` varchar(100) NOT NULL,
  `input_payload` json NOT NULL,
  `output_payload` json DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `error_message` text,
  `model` varchar(50) NOT NULL,
  `prompt_version` varchar(50) NOT NULL,
  `prompt_hash` varchar(64) NOT NULL,
  `input_tokens` int(11) DEFAULT NULL,
  `output_tokens` int(11) DEFAULT NULL,
  `total_tokens` int(11) DEFAULT NULL,
  `clinical_time_ms` int(11) DEFAULT NULL,
  `treatment_time_ms` int(11) DEFAULT NULL,
  `report_time_ms` int(11) DEFAULT NULL,
  `total_time_ms` int(11) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `estimated_cost_usd` decimal(10,6) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Estrutura da tabela `ai_prompt_versions`
--

CREATE TABLE `ai_prompt_versions` (
  `id` int(11) NOT NULL,
  `name` varchar(50) NOT NULL,
  `version` varchar(50) NOT NULL,
  `prompt_text` text NOT NULL,
  `hash` varchar(64) NOT NULL,
  `active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `alerts`
--

CREATE TABLE `alerts` (
  `id` int(11) NOT NULL,
  `clinic_id` int(11) NOT NULL DEFAULT '1',
  `patient_id` int(11) DEFAULT NULL,
  `message` text,
  `alert_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `appointments`
--

CREATE TABLE `appointments` (
  `id` int(11) NOT NULL,
  `clinic_id` int(11) NOT NULL DEFAULT '1',
  `patient_id` int(11) NOT NULL,
  `appointment_date` datetime NOT NULL,
  `status` varchar(50) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `clinics`
--

CREATE TABLE `clinics` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `slug` varchar(64) NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Estrutura da tabela `incoming_messages`
--

CREATE TABLE `incoming_messages` (
  `id` int(11) NOT NULL,
  `clinic_id` int(11) NOT NULL DEFAULT '1',
  `sender` varchar(50) DEFAULT NULL,
  `contact_name` varchar(100) DEFAULT NULL,
  `message_text` text,
  `timestamp` varchar(50) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `medical_history`
--

CREATE TABLE `medical_history` (
  `id` int(11) NOT NULL,
  `clinic_id` int(11) NOT NULL DEFAULT '1',
  `patient_id` int(11) NOT NULL,
  `history` text,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `message_status_updates`
--

CREATE TABLE `message_status_updates` (
  `id` int(11) NOT NULL,
  `clinic_id` int(11) NOT NULL DEFAULT '1',
  `message_id` varchar(100) NOT NULL,
  `status` varchar(50) NOT NULL,
  `timestamp` varchar(50) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `monitoring`
--

CREATE TABLE `monitoring` (
  `id` int(11) NOT NULL,
  `clinic_id` int(11) NOT NULL DEFAULT '1',
  `patient_id` int(11) NOT NULL,
  `status` varchar(50) DEFAULT NULL,
  `notes` text,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `patients`
--

CREATE TABLE `patients` (
  `id` int(11) NOT NULL,
  `clinic_id` int(11) NOT NULL DEFAULT '1',
  `name` varchar(100) NOT NULL,
  `email` varchar(100) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `scientific_references`
--

CREATE TABLE `scientific_references` (
  `id` int(11) NOT NULL,
  `reference_title` varchar(255) DEFAULT NULL,
  `reference_url` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `treatment_plans`
--

CREATE TABLE `treatment_plans` (
  `id` int(11) NOT NULL,
  `clinic_id` int(11) NOT NULL DEFAULT '1',
  `patient_id` int(11) NOT NULL,
  `plan_description` text,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` varchar(20) NOT NULL DEFAULT 'Medico',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------

--
-- Estrutura da tabela `user_clinics`
--

CREATE TABLE `user_clinics` (
  `user_id` int(11) NOT NULL,
  `clinic_id` int(11) NOT NULL,
  `role` enum('clinic_admin','doctor','staff','auditor') NOT NULL,
  `is_default` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Índices para tabelas despejadas
--

--
-- Índices para tabela `ai_audit_logs`
--
ALTER TABLE `ai_audit_logs`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_ai_patient` (`patient_id`),
  ADD KEY `idx_ai_request_id` (`request_id`),
  ADD KEY `idx_ai_created_at` (`created_at`),
  ADD KEY `idx_ai_status` (`status`),
  ADD KEY `idx_ai_clinic_created` (`clinic_id`,`created_at`);

--
-- Índices para tabela `ai_prompt_versions`
--
ALTER TABLE `ai_prompt_versions`
  ADD PRIMARY KEY (`id`);

--
-- Índices para tabela `alerts`
--
ALTER TABLE `alerts`
  ADD PRIMARY KEY (`id`),
  ADD KEY `patient_id` (`patient_id`),
  ADD KEY `idx_alerts_clinic` (`clinic_id`);

--
-- Índices para tabela `appointments`
--
ALTER TABLE `appointments`
  ADD PRIMARY KEY (`id`),
  ADD KEY `patient_id` (`patient_id`),
  ADD KEY `idx_appointments_clinic` (`clinic_id`);

--
-- Índices para tabela `clinics`
--
ALTER TABLE `clinics`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `slug` (`slug`);

--
-- Índices para tabela `incoming_messages`
--
ALTER TABLE `incoming_messages`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_incoming_clinic` (`clinic_id`);

--
-- Índices para tabela `medical_history`
--
ALTER TABLE `medical_history`
  ADD PRIMARY KEY (`id`),
  ADD KEY `patient_id` (`patient_id`),
  ADD KEY `idx_mh_clinic` (`clinic_id`);

--
-- Índices para tabela `message_status_updates`
--
ALTER TABLE `message_status_updates`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_msu_clinic` (`clinic_id`),
  ADD KEY `idx_msu_message_id` (`message_id`);

--
-- Índices para tabela `monitoring`
--
ALTER TABLE `monitoring`
  ADD PRIMARY KEY (`id`),
  ADD KEY `patient_id` (`patient_id`),
  ADD KEY `idx_monitoring_clinic` (`clinic_id`);

--
-- Índices para tabela `patients`
--
ALTER TABLE `patients`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_patients_clinic` (`clinic_id`);

--
-- Índices para tabela `scientific_references`
--
ALTER TABLE `scientific_references`
  ADD PRIMARY KEY (`id`);

--
-- Índices para tabela `treatment_plans`
--
ALTER TABLE `treatment_plans`
  ADD PRIMARY KEY (`id`),
  ADD KEY `patient_id` (`patient_id`),
  ADD KEY `idx_tp_clinic` (`clinic_id`);

--
-- Índices para tabela `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Índices para tabela `user_clinics`
--
ALTER TABLE `user_clinics`
  ADD PRIMARY KEY (`user_id`,`clinic_id`),
  ADD KEY `idx_uc_clinic` (`clinic_id`),
  ADD KEY `idx_uc_user` (`user_id`);

--
-- AUTO_INCREMENT de tabelas despejadas
--

--
-- AUTO_INCREMENT de tabela `ai_audit_logs`
--
ALTER TABLE `ai_audit_logs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `ai_prompt_versions`
--
ALTER TABLE `ai_prompt_versions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `alerts`
--
ALTER TABLE `alerts`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `appointments`
--
ALTER TABLE `appointments`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `clinics`
--
ALTER TABLE `clinics`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `incoming_messages`
--
ALTER TABLE `incoming_messages`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `medical_history`
--
ALTER TABLE `medical_history`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `message_status_updates`
--
ALTER TABLE `message_status_updates`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `monitoring`
--
ALTER TABLE `monitoring`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `patients`
--
ALTER TABLE `patients`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `scientific_references`
--
ALTER TABLE `scientific_references`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `treatment_plans`
--
ALTER TABLE `treatment_plans`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- Restrições para despejos de tabelas
--

--
-- Limitadores para a tabela `ai_audit_logs`
--
ALTER TABLE `ai_audit_logs`
  ADD CONSTRAINT `fk_ai_clinic` FOREIGN KEY (`clinic_id`) REFERENCES `clinics` (`id`),
  ADD CONSTRAINT `fk_ai_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`) ON DELETE CASCADE;

--
-- Limitadores para a tabela `alerts`
--
ALTER TABLE `alerts`
  ADD CONSTRAINT `alerts_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`),
  ADD CONSTRAINT `fk_alerts_clinic` FOREIGN KEY (`clinic_id`) REFERENCES `clinics` (`id`);

--
-- Limitadores para a tabela `appointments`
--
ALTER TABLE `appointments`
  ADD CONSTRAINT `appointments_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`),
  ADD CONSTRAINT `fk_appointments_clinic` FOREIGN KEY (`clinic_id`) REFERENCES `clinics` (`id`);

--
-- Limitadores para a tabela `incoming_messages`
--
ALTER TABLE `incoming_messages`
  ADD CONSTRAINT `fk_incoming_clinic` FOREIGN KEY (`clinic_id`) REFERENCES `clinics` (`id`);

--
-- Limitadores para a tabela `medical_history`
--
ALTER TABLE `medical_history`
  ADD CONSTRAINT `fk_mh_clinic` FOREIGN KEY (`clinic_id`) REFERENCES `clinics` (`id`),
  ADD CONSTRAINT `medical_history_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`);

--
-- Limitadores para a tabela `message_status_updates`
--
ALTER TABLE `message_status_updates`
  ADD CONSTRAINT `fk_msu_clinic` FOREIGN KEY (`clinic_id`) REFERENCES `clinics` (`id`);

--
-- Limitadores para a tabela `monitoring`
--
ALTER TABLE `monitoring`
  ADD CONSTRAINT `fk_monitoring_clinic` FOREIGN KEY (`clinic_id`) REFERENCES `clinics` (`id`),
  ADD CONSTRAINT `monitoring_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`);

--
-- Limitadores para a tabela `patients`
--
ALTER TABLE `patients`
  ADD CONSTRAINT `fk_patients_clinic` FOREIGN KEY (`clinic_id`) REFERENCES `clinics` (`id`);

--
-- Limitadores para a tabela `treatment_plans`
--
ALTER TABLE `treatment_plans`
  ADD CONSTRAINT `fk_tp_clinic` FOREIGN KEY (`clinic_id`) REFERENCES `clinics` (`id`),
  ADD CONSTRAINT `treatment_plans_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`);

--
-- Limitadores para a tabela `user_clinics`
--
ALTER TABLE `user_clinics`
  ADD CONSTRAINT `fk_uc_clinic` FOREIGN KEY (`clinic_id`) REFERENCES `clinics` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_uc_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;
