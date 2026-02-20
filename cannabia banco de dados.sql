-- phpMyAdmin SQL Dump
-- version 5.1.2
-- https://www.phpmyadmin.net/
--
-- Host: localhost:3306
-- Tempo de geração: 20-Fev-2026 às 00:18
-- Versão do servidor: 5.7.24
-- versão do PHP: 8.3.1

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
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
-- Estrutura da tabela `alerts`
--

CREATE TABLE `alerts` (
  `id` int(11) NOT NULL,
  `patient_id` int(11) DEFAULT NULL,
  `message` text,
  `alert_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Extraindo dados da tabela `alerts`
--

INSERT INTO `alerts` (`id`, `patient_id`, `message`, `alert_time`, `created_at`) VALUES
(1, 1, 'Lembrete: Sua consulta está agendada para amanhã. Por favor, confirme sua presença.', '2025-03-13 17:31:25', '2025-03-12 17:31:25');

-- --------------------------------------------------------

--
-- Estrutura da tabela `appointments`
--

CREATE TABLE `appointments` (
  `id` int(11) NOT NULL,
  `patient_id` int(11) NOT NULL,
  `appointment_date` datetime NOT NULL,
  `status` varchar(50) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Estrutura da tabela `incoming_messages`
--

CREATE TABLE `incoming_messages` (
  `id` int(11) NOT NULL,
  `sender` varchar(50) DEFAULT NULL,
  `contact_name` varchar(100) DEFAULT NULL,
  `message_text` text,
  `timestamp` varchar(50) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Extraindo dados da tabela `incoming_messages`
--

INSERT INTO `incoming_messages` (`id`, `sender`, `contact_name`, `message_text`, `timestamp`) VALUES
(1, '556282810427', 'André Luiz', 'Td bem?', '1741823028'),
(2, '556282810427', 'André Luiz', 'Oi', '1741823161'),
(3, '556282810427', 'André Luiz', 'Oi', '1741826146'),
(4, '556282810427', 'André Luiz', 'Boa noite', '1741826157'),
(5, '556282810427', 'André Luiz', 'Quero saber sobre o tratamento com cannabis', '1741826924');

-- --------------------------------------------------------

--
-- Estrutura da tabela `medical_history`
--

CREATE TABLE `medical_history` (
  `id` int(11) NOT NULL,
  `patient_id` int(11) NOT NULL,
  `history` text,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Extraindo dados da tabela `medical_history`
--

INSERT INTO `medical_history` (`id`, `patient_id`, `history`, `created_at`) VALUES
(1, 1, '\n\nNome do paciente: João Silva\nData de nascimento: 10/05/1985\nIdade: 35 anos\nGênero: Masculino\n\nHistórico médico:\n- Doenças prévias: O paciente João Silva não possui histórico de doenças prévias significativas. Ele teve apenas algumas infecções respiratórias leves durante a infância.\n\nMedicações:\n- Atualmente, o paciente não está tomando nenhuma medicação regularmente.\n- No passado, ele tomou paracetamol para tratar dores de cabeça ocasionais.\n- Também foi prescrito um antibiótico por 10 dias para tratar uma infecção urinária em 2018.\n\nAlergias:\n- O paciente possui alergia a sulfa, relatando reações alérgicas graves, como urticária e dificuldade para respirar, quando exposto a esse componente.\n\nOutros detalhes relevantes:\n- O paciente é fumante de cigarros há 10 anos, mas recentemente começou a usar cannabis para fins recreativos.\n- Ele relata ter uma alimentação saudável', '2025-03-12 17:28:33');

-- --------------------------------------------------------

--
-- Estrutura da tabela `monitoring`
--

CREATE TABLE `monitoring` (
  `id` int(11) NOT NULL,
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
  `name` varchar(100) NOT NULL,
  `email` varchar(100) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Extraindo dados da tabela `patients`
--

INSERT INTO `patients` (`id`, `name`, `email`, `phone`, `created_at`) VALUES
(1, 'João Silva', 'joao@example.com', '123456789', '2025-03-12 17:19:05');

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
  `patient_id` int(11) NOT NULL,
  `plan_description` text,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Extraindo dados da tabela `treatment_plans`
--

INSERT INTO `treatment_plans` (`id`, `patient_id`, `plan_description`, `created_at`) VALUES
(1, 1, '\n\nPlano de Tratamento para João Silva:\n\nHistórico médico:\n- João Silva, 45 anos\n- Diagnóstico de esclerose múltipla em 2016\n- Sintomas: dor crônica, espasticidade muscular, fadiga, distúrbios do sono, ansiedade e depressão\n- Atualmente em tratamento com medicamentos convencionais, mas com efeitos colaterais significativos e pouca melhora nos sintomas\n\nSugestão de tratamento com canabinoides:\n1. Iniciar com uma proporção de 1:1 de CBD (cannabidiol) e THC (tetra-hidrocanabinol), com baixa dosagem (5 mg de cada) duas vezes ao dia. Esta proporção é ideal para tratar a dor crônica e espasticidade muscular, além de ajudar a melhorar o sono e a ansiedade.\n\n2. Caso não haja melhora significativa nos sintomas após duas semanas, aumentar gradualmente a dosagem de THC até atingir 10 mg duas vezes ao dia. O THC tem propriedades analgés', '2025-03-12 17:29:02');

--
-- Índices para tabelas despejadas
--

--
-- Índices para tabela `alerts`
--
ALTER TABLE `alerts`
  ADD PRIMARY KEY (`id`),
  ADD KEY `patient_id` (`patient_id`);

--
-- Índices para tabela `appointments`
--
ALTER TABLE `appointments`
  ADD PRIMARY KEY (`id`),
  ADD KEY `patient_id` (`patient_id`);

--
-- Índices para tabela `incoming_messages`
--
ALTER TABLE `incoming_messages`
  ADD PRIMARY KEY (`id`);

--
-- Índices para tabela `medical_history`
--
ALTER TABLE `medical_history`
  ADD PRIMARY KEY (`id`),
  ADD KEY `patient_id` (`patient_id`);

--
-- Índices para tabela `monitoring`
--
ALTER TABLE `monitoring`
  ADD PRIMARY KEY (`id`),
  ADD KEY `patient_id` (`patient_id`);

--
-- Índices para tabela `patients`
--
ALTER TABLE `patients`
  ADD PRIMARY KEY (`id`);

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
  ADD KEY `patient_id` (`patient_id`);

--
-- AUTO_INCREMENT de tabelas despejadas
--

--
-- AUTO_INCREMENT de tabela `alerts`
--
ALTER TABLE `alerts`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de tabela `appointments`
--
ALTER TABLE `appointments`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `incoming_messages`
--
ALTER TABLE `incoming_messages`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT de tabela `medical_history`
--
ALTER TABLE `medical_history`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de tabela `monitoring`
--
ALTER TABLE `monitoring`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `patients`
--
ALTER TABLE `patients`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de tabela `scientific_references`
--
ALTER TABLE `scientific_references`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `treatment_plans`
--
ALTER TABLE `treatment_plans`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- Restrições para despejos de tabelas
--

--
-- Limitadores para a tabela `alerts`
--
ALTER TABLE `alerts`
  ADD CONSTRAINT `alerts_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`);

--
-- Limitadores para a tabela `appointments`
--
ALTER TABLE `appointments`
  ADD CONSTRAINT `appointments_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`);

--
-- Limitadores para a tabela `medical_history`
--
ALTER TABLE `medical_history`
  ADD CONSTRAINT `medical_history_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`);

--
-- Limitadores para a tabela `monitoring`
--
ALTER TABLE `monitoring`
  ADD CONSTRAINT `monitoring_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`);

--
-- Limitadores para a tabela `treatment_plans`
--
ALTER TABLE `treatment_plans`
  ADD CONSTRAINT `treatment_plans_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
